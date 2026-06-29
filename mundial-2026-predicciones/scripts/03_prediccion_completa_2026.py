def crear_mapa_clasificados(tabla_grupos):
    """
    Crea estructuras para resolver slots de eliminación directa.

    Incluye:
    - primeros de grupo
    - segundos de grupo
    - mejores terceros
    - clasificados por código
    - lista de clasificados disponibles para fallback
    """
    tabla = tabla_grupos.copy()

    mapa = {
        "primeros": {},
        "segundos": {},
        "terceros": {},
        "terceros_disponibles": [],
        "clasificados_por_codigo": {},
        "clasificados_disponibles": [],
    }

    for _, row in tabla.iterrows():
        info = {
            "equipo": row["seleccion"],
            "codigo": row["codigo"],
            "grupo": row["grupo"],
            "posicion_grupo": row["posicion_grupo"],
            "tipo_clasificacion": row["tipo_clasificacion"],
            "pts": row["pts"],
            "dg": row["dg"],
            "gf": row["gf"],
            "ranking_aux": row["ranking_aux"],
            "origen_resolucion": "tabla_grupos",
        }

        if row["clasifica"] == "Sí":
            mapa["clasificados_por_codigo"][row["codigo"]] = info
            mapa["clasificados_disponibles"].append(info)

        if row["posicion_grupo"] == 1:
            mapa["primeros"][row["grupo"]] = info

        elif row["posicion_grupo"] == 2:
            mapa["segundos"][row["grupo"]] = info

        elif row["posicion_grupo"] == 3 and row["clasifica"] == "Sí":
            mapa["terceros"][row["grupo"]] = info
            mapa["terceros_disponibles"].append(info)

    mapa["terceros_disponibles"] = sorted(
        mapa["terceros_disponibles"],
        key=lambda x: (x["pts"], x["dg"], x["gf"], x["ranking_aux"]),
        reverse=True,
    )

    mapa["clasificados_disponibles"] = sorted(
        mapa["clasificados_disponibles"],
        key=lambda x: (
            x["posicion_grupo"],
            -x["pts"],
            -x["dg"],
            -x["gf"],
            -x["ranking_aux"],
        ),
    )

    return mapa
