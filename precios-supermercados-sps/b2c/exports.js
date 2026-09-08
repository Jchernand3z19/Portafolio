const DISCLAIMER = "Total estimado calculado con los precios públicos observados en cada supermercado. Los precios pueden cambiar en tienda.";

function minorToDecimal(minor) {
  return Number.isSafeInteger(minor) ? (minor / 100).toFixed(2) : "";
}

function csvCell(value) {
  let text = String(value ?? "");
  if (/^[\t\r\n ]*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

function sortedRetailers(summary) {
  if (!(summary?.retailers instanceof Map)) throw new TypeError("cart_summary_retailers_invalid");
  return [...summary.retailers].sort(([left], [right]) => String(left).localeCompare(String(right)));
}

export function buildCartCsv(summary) {
  const rows = [[
    "producto", "marca", "presentacion", "supermercado", "ubicacion", "cantidad",
    "precio_unitario_hnl", "total_linea_hnl", "estado", "freshness", "observado_en", "comprado",
  ]];
  for (const [retailer, group] of sortedRetailers(summary)) {
    for (const line of group.lines ?? []) {
      rows.push([
        line.product_name,
        line.brand ?? "",
        line.presentation ?? "",
        retailer,
        line.location_id ?? "",
        line.quantity,
        minorToDecimal(line.unit_price_minor),
        line.line_total_minor === null ? "" : minorToDecimal(line.line_total_minor),
        line.invalid ? "NO_DISPONIBLE" : "DISPONIBLE",
        line.freshness_status ?? "",
        line.observed_at ?? "",
        line.checked ? "SI" : "NO",
      ]);
    }
  }
  return `\uFEFF${rows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`;
}

function latin1Safe(value) {
  return String(value ?? "")
    .replace(/[–—]/g, "-")
    .replace(/…/g, "...")
    .replace(/×/g, "x")
    .replace(/[^\u0000-\u00ff]/g, "?");
}

function latin1Bytes(value) {
  const text = latin1Safe(value);
  const bytes = new Uint8Array(text.length);
  for (let index = 0; index < text.length; index += 1) bytes[index] = text.charCodeAt(index);
  return bytes;
}

function concatBytes(chunks) {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const result = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

function pdfEscape(value) {
  return latin1Safe(value).replaceAll("\\", "\\\\").replaceAll("(", "\\(").replaceAll(")", "\\)");
}

function wrapText(value, max = 88) {
  const words = latin1Safe(value).split(/\s+/).filter(Boolean);
  if (!words.length) return [""];
  const lines = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= max) current = candidate;
    else {
      if (current) lines.push(current);
      current = word.length <= max ? word : word.slice(0, max);
    }
  }
  if (current) lines.push(current);
  return lines;
}

function pdfLogicalLines(summary, generatedAt) {
  const generated = generatedAt instanceof Date ? generatedAt : new Date(generatedAt);
  if (Number.isNaN(generated.getTime())) throw new TypeError("generated_at_invalid");
  const lines = [
    {text: "MI COMPRA - Compra Inteligente", bold: true, size: 16},
    {text: `Generado: ${generated.toISOString()}`, bold: false, size: 9},
    {text: `Productos: ${summary.products} | Unidades: ${summary.units} | Supermercados: ${summary.retailer_count}`, bold: false, size: 10},
    {text: "", bold: false, size: 8},
  ];
  for (const [retailer, group] of sortedRetailers(summary)) {
    lines.push({text: String(retailer).replaceAll("_", " ").toLocaleUpperCase("es"), bold: true, size: 12});
    for (const line of group.lines ?? []) {
      for (const part of wrapText([line.product_name, line.brand, line.presentation].filter(Boolean).join(" - "))) {
        lines.push({text: part, bold: true, size: 10});
      }
      const total = line.line_total_minor === null ? "INCOMPLETO" : `L ${minorToDecimal(line.line_total_minor)}`;
      lines.push({
        text: `Cant. ${line.quantity} | Unit. L ${minorToDecimal(line.unit_price_minor)} | Total ${total} | ${line.freshness_status ?? "SIN_FRESHNESS"}`,
        bold: false,
        size: 9,
      });
      if (line.invalid) lines.push({text: "Oferta no disponible; se conserva el último precio guardado sólo como referencia.", bold: false, size: 9});
    }
    lines.push({
      text: group.incomplete ? "Subtotal: INCOMPLETO" : `Subtotal: L ${minorToDecimal(group.subtotal_minor)}`,
      bold: true,
      size: 10,
    });
    lines.push({text: "", bold: false, size: 8});
  }
  lines.push({
    text: summary.grand_total_minor === null
      ? "TOTAL ESTIMADO DE MI COMPRA: INCOMPLETO"
      : `TOTAL ESTIMADO DE MI COMPRA: L ${minorToDecimal(summary.grand_total_minor)}`,
    bold: true,
    size: 13,
  });
  if (summary.stale) lines.push({text: `Advertencia: ${summary.stale} precio(s) con freshness STALE.`, bold: false, size: 9});
  for (const part of wrapText(DISCLAIMER, 82)) lines.push({text: part, bold: false, size: 9});
  return lines;
}

function paginate(lines) {
  const pages = [[]];
  let y = 794;
  for (const line of lines) {
    const step = line.text ? line.size + 5 : 9;
    if (y - step < 48) {
      pages.push([{text: "MI COMPRA - continuación", bold: true, size: 11, y: 794}]);
      y = 774;
    }
    pages.at(-1).push({...line, y});
    y -= step;
  }
  return pages;
}

function contentStream(page) {
  return page.map((line) => {
    if (!line.text) return "";
    const font = line.bold ? "F2" : "F1";
    return `BT /${font} ${line.size} Tf 1 0 0 1 48 ${line.y} Tm (${pdfEscape(line.text)}) Tj ET`;
  }).filter(Boolean).join("\n");
}

export function buildCartPdf(summary, generatedAt = new Date()) {
  const pages = paginate(pdfLogicalLines(summary, generatedAt));
  const objectCount = 4 + pages.length * 2;
  const objects = new Array(objectCount + 1);
  objects[1] = latin1Bytes("<< /Type /Catalog /Pages 2 0 R >>");
  const pageRefs = pages.map((_, index) => `${5 + index * 2} 0 R`).join(" ");
  objects[2] = latin1Bytes(`<< /Type /Pages /Count ${pages.length} /Kids [${pageRefs}] >>`);
  objects[3] = latin1Bytes("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
  objects[4] = latin1Bytes("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>");
  pages.forEach((page, index) => {
    const pageObject = 5 + index * 2;
    const contentObject = pageObject + 1;
    const stream = latin1Bytes(contentStream(page));
    objects[pageObject] = latin1Bytes(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${contentObject} 0 R >>`);
    objects[contentObject] = concatBytes([
      latin1Bytes(`<< /Length ${stream.length} >>\nstream\n`),
      stream,
      latin1Bytes("\nendstream"),
    ]);
  });

  const chunks = [latin1Bytes("%PDF-1.4\n%âãÏÓ\n")];
  const offsets = new Array(objectCount + 1).fill(0);
  let offset = chunks[0].length;
  for (let index = 1; index <= objectCount; index += 1) {
    offsets[index] = offset;
    const object = concatBytes([
      latin1Bytes(`${index} 0 obj\n`),
      objects[index],
      latin1Bytes("\nendobj\n"),
    ]);
    chunks.push(object);
    offset += object.length;
  }
  const xrefOffset = offset;
  const xref = [
    `xref\n0 ${objectCount + 1}\n`,
    "0000000000 65535 f \n",
    ...offsets.slice(1).map((value) => `${String(value).padStart(10, "0")} 00000 n \n`),
    `trailer\n<< /Size ${objectCount + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`,
  ].join("");
  chunks.push(latin1Bytes(xref));
  return concatBytes(chunks);
}

export {DISCLAIMER};
