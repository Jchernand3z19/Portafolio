const select = document.getElementById("city-filter");

if (select) {
  const current = document.body?.dataset.citySlug || "san-pedro-sula";
  select.value = current;
  select.addEventListener("change", () => {
    const target = select.value;
    if (target === current) return;
    const relative = target === "tegucigalpa"
      ? (current === "tegucigalpa" ? "./" : "tegucigalpa/")
      : (current === "tegucigalpa" ? "../" : "./");
    window.location.assign(new URL(relative, window.location.href));
  });
}
