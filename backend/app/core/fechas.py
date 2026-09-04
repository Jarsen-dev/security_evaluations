"""Aritmética de meses de calendario.

Vive aparte porque la usan dos módulos que no deberían depender uno del otro:
los avisos de vencimiento de Estudios y los de Extintores. Un `timedelta` de
treinta días **no** sirve aquí: "un mes antes" son treinta y tantos días según
el mes, y la ventana del aviso tiene que caer en el día equivalente.
"""

from datetime import date


def dias_del_mes(ano: int, mes: int) -> int:
    """Cuántos días tiene un mes, sin importar `calendar`."""
    if mes == 2:
        bisiesto = ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)
        return 29 if bisiesto else 28
    return 30 if mes in (4, 6, 9, 11) else 31


def sumar_meses(dia: date, meses: int) -> date:
    """El mismo día, `meses` meses después, ajustando el fin de mes.

    El 31 de enero más un mes es el 28 (o el 29) de febrero, que es el último
    día equivalente que existe.

    **Se cuenta desde la fecha original, no encadenando meses de uno en uno.**
    Encadenar se desvía: 31 de enero → 28 de febrero → 28 de marzo, cuando dos
    meses después del 31 de enero es el 31 de marzo. Esa deriva movería tres
    días la frontera del semáforo de los extintores.
    """
    total = dia.month - 1 + meses
    ano = dia.year + total // 12
    mes = total % 12 + 1

    return date(ano, mes, min(dia.day, dias_del_mes(ano, mes)))
