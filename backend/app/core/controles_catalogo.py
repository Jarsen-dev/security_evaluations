"""Catálogo de los controles ESH: puntos de inspección y rangos de operación.

Mismo criterio que ``AREAS`` en ``constants.py``: los textos viven aquí y en
ningún otro lado. El frontend los obtiene por la API
(``/api/controles/sqp/catalogo``, ``/api/controles/checklist/{control}/catalogo``)
para que nunca queden escritos a mano en dos lugares.

Las preguntas se transcriben del formato en papel (hoja "Inspeccion de SQP" del
libro de inspecciones). Se conserva su numeración original **tal cual**, con sus
rarezas incluidas: hay dos puntos numerados ``2.2`` y el ``3.9`` aparece
intercalado antes del ``3.6``. El orden lo fija la posición en esta tupla, no el
código, justo para que esas rarezas no lo alteren.
"""

from decimal import Decimal
from typing import Final, Literal, NamedTuple

# --- Rayser: presión de los manómetros -------------------------------------
#
# La hoja en papel lo dice al pie: "La presión normal de los manómetros es de
# 130 psi". El semáforo abre 5 psi hacia cada lado.
RAYSER_NORMAL: Final[Decimal] = Decimal("130")
RAYSER_MINIMO: Final[Decimal] = Decimal("125")
RAYSER_MAXIMO: Final[Decimal] = Decimal("135")

# Tope de captura. No es el rango bueno, es lo que puede marcar el instrumento:
# un valor de 4 dígitos es un dedazo, no una lectura.
RAYSER_TOPE: Final[Decimal] = Decimal("300")

# Cuántos manómetros tiene el equipo.
RAYSER_MANOMETROS: Final[int] = 4

Semaforo = Literal["verde", "rojo", "naranja"]


def semaforo(valor: Decimal) -> Semaforo:
    """Clasifica la lectura de un manómetro.

    Verde dentro de 125–135 psi, rojo por debajo y naranja por encima. Se
    calcula siempre en el servidor: el cliente lo repite solo para pintar el
    formulario mientras se teclea.
    """
    if valor < RAYSER_MINIMO:
        return "rojo"
    if valor > RAYSER_MAXIMO:
        return "naranja"
    return "verde"


def fuera_de_rango(valores: list[Decimal]) -> bool:
    """``True`` si alguna lectura salió del rango normal.

    Cuando ocurre, el registro exige foto de evidencia y observaciones.
    """
    return any(semaforo(valor) != "verde" for valor in valores)


# --- Inspección de sustancias químicas peligrosas (SQP) --------------------


class PuntoSqp(NamedTuple):
    """Un punto de la inspección de SQP."""

    codigo: str
    seccion: str
    texto: str


SECCIONES_SQP: Final[tuple[str, ...]] = (
    "1. DOCUMENTACIÓN",
    "2. IDENTIFICACIÓN",
    "3. INSTALACIONES",
    "4. ALMACENAMIENTO",
)

PUNTOS_SQP: Final[tuple[PuntoSqp, ...]] = (
    PuntoSqp(
        "1.1",
        SECCIONES_SQP[0],
        "¿Cuenta con Hojas de Datos de Seguridad (MSDS) de las sustancias "
        "químicas en sitio?",
    ),
    PuntoSqp("1.2", SECCIONES_SQP[0], "¿Las MSDS se encuentran en el idioma español?"),
    PuntoSqp(
        "1.3", SECCIONES_SQP[0], "¿Cuentan con matriz de compatibilidad de materiales?"
    ),
    PuntoSqp(
        "1.4",
        SECCIONES_SQP[0],
        "¿Existen procedimientos para el manejo de sustancias químicas?",
    ),
    PuntoSqp("2.1", SECCIONES_SQP[1], "¿Hay señalización de la zona de almacenamiento?"),
    PuntoSqp(
        "2.2",
        SECCIONES_SQP[1],
        "¿Las sustancias químicas se encuentran claramente identificadas y con "
        "su etiqueta de seguridad?",
    ),
    PuntoSqp(
        "2.2",
        SECCIONES_SQP[1],
        "¿El personal que manipula sustancias químicas identifica a través de "
        "pictogramas los riesgos de los productos y el uso adecuado de EPP?",
    ),
    PuntoSqp(
        "3.1",
        SECCIONES_SQP[2],
        "¿Cuentan con zona y/o área exclusiva para almacenamiento de sustancias "
        "químicas?",
    ),
    PuntoSqp(
        "3.2",
        SECCIONES_SQP[2],
        "¿Cuentan con zona exclusiva para almacenamiento de residuos?",
    ),
    PuntoSqp(
        "3.3",
        SECCIONES_SQP[2],
        "¿Las áreas de almacenamiento se encuentran separadas de las zonas de "
        "alimentación e hidratación del personal?",
    ),
    PuntoSqp(
        "3.4", SECCIONES_SQP[2], "¿Las instalaciones de almacenamiento están ventiladas?"
    ),
    PuntoSqp(
        "3.5",
        SECCIONES_SQP[2],
        "¿La zona de almacenamiento cuenta con buena iluminación?",
    ),
    PuntoSqp(
        "3.9",
        SECCIONES_SQP[2],
        "¿Hay protección y correcto aislamiento de las conexiones eléctricas?",
    ),
    PuntoSqp(
        "3.6", SECCIONES_SQP[2], "¿Se cuenta con lava ojos dentro del área o cerca al sitio?"
    ),
    PuntoSqp(
        "3.7",
        SECCIONES_SQP[2],
        "¿Se cuenta con sistemas de respuesta a emergencias cerca al sitio "
        "(extintores, kit de derrames)?",
    ),
    PuntoSqp(
        "4.1", SECCIONES_SQP[3], "¿Los envases de los productos están en buen estado?"
    ),
    PuntoSqp(
        "4.2",
        SECCIONES_SQP[3],
        "¿Los productos químicos están segregados y separados según su "
        "compatibilidad?",
    ),
    PuntoSqp(
        "4.3",
        SECCIONES_SQP[3],
        "¿Todas las etiquetas de los productos químicos son legibles?",
    ),
    PuntoSqp(
        "4.4",
        SECCIONES_SQP[3],
        "¿Los contenedores de las sustancias químicas vacíos o dañados son "
        "desechados adecuadamente?",
    ),
    PuntoSqp(
        "4.5",
        SECCIONES_SQP[3],
        "¿El área de almacenamiento está ordenada y libre de derrames o fugas?",
    ),
    PuntoSqp(
        "4.6",
        SECCIONES_SQP[3],
        "¿Los cilindros que contienen gases inflamables tienen las cadenas de "
        "ajuste recubiertas de plástico o sistema anti chispa?",
    ),
    PuntoSqp(
        "4.7",
        SECCIONES_SQP[3],
        "¿Para el almacenamiento de cilindros hay espacios definidos?",
    ),
    PuntoSqp(
        "4.8",
        SECCIONES_SQP[3],
        "¿Tiene separados e identificados los cilindros llenos de los vacíos?",
    ),
)

TOTAL_PUNTOS_SQP: Final[int] = len(PUNTOS_SQP)

# Renglones numerados de la tabla "Nombre de la SQP" al pie del formato. El
# usuario captura las sustancias en un campo libre, una por renglón; esto es
# cuántos caben en la hoja impresa.
RENGLONES_SUSTANCIAS: Final[int] = 15

VALORES_SQP: Final[frozenset[str]] = frozenset({"si", "no", "na"})

# Cómo se rotula cada respuesta en la hoja de Excel.
ETIQUETAS_VALOR_SQP: Final[dict[str, str]] = {
    "si": "SI",
    "no": "NO",
    "na": "N/A",
}


# --- Controles de lista de verificación (OK / NO OK) -----------------------
#
# Tres hojas del libro de inspecciones tienen exactamente la misma forma: una
# fila por día del mes y una columna por punto, que se palomea o se marca. Solo
# cambian el título y la lista de puntos, así que se describen aquí y el
# formulario, la tabla y el Excel se escriben una sola vez.


class PuntoControl(NamedTuple):
    """Un punto de una lista de verificación.

    Los campos opcionales solo los usan los formatos por inspección: las tres
    hojas de rejilla mensual no tienen ni categorías ni mediciones, y sus
    puntos están escritos únicamente en español.
    """

    clave: str
    etiqueta: str
    # Texto coreano del formato bilingüe. El panel muestra uno u otro según su
    # idioma; el Excel siempre imprime los dos, como la hoja impresa.
    etiqueta_ko: str | None = None
    # Agrupación del punto dentro de la hoja ("출입 / Acceso").
    categoria: str | None = None
    # Rótulo de la medición que acompaña al punto ("°C", "ΔT °C"). Si está,
    # el valor es obligatorio.
    medicion: str | None = None


# Tipos de campo que puede traer el encabezado o una sección del formato.
TiposCampo = Literal["texto", "texto_largo", "hora", "numero", "opcion"]


class CampoFormato(NamedTuple):
    """Un campo del encabezado o de una sección del formato."""

    clave: str
    etiqueta: str
    etiqueta_ko: str | None = None
    tipo: TiposCampo = "texto"
    # Valores permitidos cuando el tipo es "opcion".
    opciones: tuple[str, ...] = ()
    # Unidad que se muestra junto a un campo numérico.
    unidad: str | None = None
    obligatorio: bool = True


class SeccionFormato(NamedTuple):
    """Un bloque del formato que va después de la lista de puntos."""

    clave: str
    titulo: str
    titulo_ko: str | None = None
    campos: tuple[CampoFormato, ...] = ()
    # El bloque de acción ante anomalía solo tiene sentido cuando algo salió
    # mal: se muestra y se exige únicamente si hay algún punto en NO.
    solo_con_hallazgos: bool = False


class DefinicionChecklist(NamedTuple):
    """Una hoja de lista de verificación completa.

    Cubre las dos formas que tienen estos controles:

    * **Rejilla mensual** (almacén de RP's, recorridos, muro): una fila por día
      del mes y una columna por punto. Sin encabezado ni secciones, y con una
      sola hoja por día.
    * **Formato por inspección** (silos, tableros): cada registro es una hoja
      completa con su encabezado, y un mismo día admite varias —una por turno,
      o una por tablero y turno—.

    Lo que distingue a las dos es si la definición trae ``encabezado``.
    """

    clave: str
    titulo: str
    # Nombre de la pestaña dentro del Excel: Excel corta a 31 caracteres y no
    # admite : \\ / ? * [ ], así que se escribe a mano en vez de recortar el
    # título.
    hoja: str
    # Solo la revisión de muros lleva una pregunta bajo el título; en las otras
    # dos hojas el título ya dice todo.
    subtitulo: str | None
    puntos: tuple[PuntoControl, ...]
    titulo_ko: str | None = None
    # Cómo se rotulan las dos respuestas posibles.
    estilo_valores: Literal["ok_no_ok", "si_no"] = "ok_no_ok"
    encabezado: tuple[CampoFormato, ...] = ()
    secciones: tuple[SeccionFormato, ...] = ()
    # Campos del encabezado que, junto con la fecha, identifican una
    # inspección. Vacío = una sola por día.
    clave_unicidad: tuple[str, ...] = ()
    # Aviso al pie de la hoja impresa.
    nota: str | None = None
    nota_ko: str | None = None


CONTROLES_CHECKLIST: Final[dict[str, DefinicionChecklist]] = {
    "almacen_rp": DefinicionChecklist(
        clave="almacen_rp",
        titulo="CONTROL DE ALMACEN DE RESIDUOS PELIGROSOS",
        hoja="Almacen de RP",
        subtitulo=None,
        puntos=(
            PuntoControl("derrames", "Derrames de residuos"),
            PuntoControl("extintor", "Extintor en buenas condiciones"),
            PuntoControl("kit_derrames", "Kit de control de derrames"),
            PuntoControl("senalizacion", "Señalización"),
            PuntoControl("charolas", "Charolas"),
            PuntoControl("tierras", "Tierras físicas"),
        ),
    ),
    "recorridos": DefinicionChecklist(
        clave="recorridos",
        titulo="CONTROL DE RECORRIDO",
        hoja="Recorridos",
        subtitulo=None,
        puntos=(
            PuntoControl("frente", "Frente"),
            PuntoControl("oeste", "Lado oeste"),
            PuntoControl("trasera", "Parte trasera"),
            PuntoControl("este", "Lado este"),
        ),
    ),
    "muro": DefinicionChecklist(
        clave="muro",
        titulo="REVISION DE MUROS ALMACEN-EPS",
        hoja="Revision muro",
        subtitulo="¿Muro sin daño o fisura?",
        puntos=(
            PuntoControl("zona_1", "Zona 1"),
            PuntoControl("zona_2", "Zona 2"),
            PuntoControl("zona_3", "Zona 3"),
            PuntoControl("zona_4", "Zona 4"),
        ),
    ),
    "silos": DefinicionChecklist(
        clave="silos",
        titulo="Lista de Verificación Diaria de Seguridad – Cuarto de Silos EPS",
        titulo_ko="EPS 공장 사일로실 일일 안전점검 체크시트",
        hoja="Silos EPS",
        subtitulo=None,
        estilo_valores="si_no",
        encabezado=(
            CampoFormato(clave="planta", etiqueta="Planta", etiqueta_ko="공장"),
            CampoFormato(
            clave="turno",
            etiqueta="Turno",
            etiqueta_ko="근무조",
            tipo="opcion",
            opciones=("Día", "Noche"),
        ),
            CampoFormato(
                clave="hora", etiqueta="Hora de inspección", etiqueta_ko="점검시간",
                tipo="hora",
            ),
            CampoFormato(clave="inspector", etiqueta="Inspector", etiqueta_ko="점검자"),
            CampoFormato(
                clave="supervisor", etiqueta="Supervisor", etiqueta_ko="확인자",
                obligatorio=False,
            ),
        ),
        # Una inspección por turno: repetir el turno el mismo día es un error
        # de captura, no una inspección nueva.
        clave_unicidad=("turno",),
        secciones=(
            SeccionFormato(
                clave="anomalia",
                titulo="Acción en caso de anomalía",
                titulo_ko="이상 발생 시 조치",
                solo_con_hallazgos=True,
                campos=(
                    CampoFormato(
                        clave="hora_deteccion", etiqueta="Hora de detección",
                        etiqueta_ko="이상 발견 시간", tipo="hora",
                    ),
                    CampoFormato(
                        clave="equipo", etiqueta="Equipo y ubicación",
                        etiqueta_ko="설비 및 위치",
                    ),
                    CampoFormato(
                        clave="descripcion", etiqueta="Descripción de la anomalía",
                        etiqueta_ko="이상 내용", tipo="texto_largo",
                    ),
                    CampoFormato(
                        clave="accion_inmediata",
                        etiqueta="Acción inmediata realizada",
                        etiqueta_ko="즉시 조치 내용", tipo="texto_largo",
                    ),
                    CampoFormato(
                        clave="responsable_accion",
                        etiqueta="Departamento o persona responsable",
                        etiqueta_ko="담당 부서·담당자",
                    ),
                    CampoFormato(
                        clave="hora_cierre", etiqueta="Hora de cierre",
                        etiqueta_ko="조치 완료 시간", tipo="hora", obligatorio=False,
                    ),
                    CampoFormato(
                        clave="pendiente", etiqueta="Acción pendiente",
                        etiqueta_ko="미조치 사항", tipo="texto_largo",
                        obligatorio=False,
                    ),
                ),
            ),
            SeccionFormato(
                clave="cierre",
                titulo="Confirmación diaria",
                titulo_ko="일일 최종 확인",
                campos=(
                    CampoFormato(
                        clave="resultado", etiqueta="Resultado final",
                        etiqueta_ko="점검 결과", tipo="opcion",
                        opciones=(
                            "Sin anomalías",
                            "Anomalía detectada y corregida",
                            "Acción pendiente",
                        ),
                    ),
                ),
            ),
        ),
        puntos=(
        PuntoControl(
            clave="p01",
            etiqueta=(
                "¿Las entradas y pasillos del cuarto de silos están libres de "
                "obstáculos?"
            ),
            etiqueta_ko="사일로실 출입구 및 통로에 장애물이 없는가?",
            categoria="출입 / Acceso",
        ),
        PuntoControl(
            clave="p02",
            etiqueta=(
                "¿La señalización de seguridad y de acceso restringido está "
                "colocada correctamente?"
            ),
            etiqueta_ko="관계자 외 출입금지 및 안전표지가 정상 부착되어 있는가?",
            categoria="출입 / Acceso",
        ),
        PuntoControl(
            clave="p03",
            etiqueta=(
                "¿Los pasillos están libres de materia prima EPS y otros "
                "materiales?"
            ),
            etiqueta_ko="EPS 원료 및 기타 물품이 통로에 방치되어 있지 않은가?",
            categoria="정리정돈 / Orden",
        ),
        PuntoControl(
            clave="p04",
            etiqueta=(
                "¿El piso está libre de perlas de EPS, empaques u otros materiales "
                "que puedan provocar caídas?"
            ),
            etiqueta_ko="바닥에 EPS 비드, 포장재 등으로 인한 미끄럼·넘어짐 위험이 없는가?",
            categoria="정리정돈 / Orden",
        ),
        PuntoControl(
            clave="p05",
            etiqueta=(
                "¿El área está libre de fuentes de ignición y evidencia de NO "
                "FUMAR?"
            ),
            etiqueta_ko="사일로실 내부 및 주변에 화기·흡연 흔적이 없는가?",
            categoria="화재 / Incendio",
        ),
        PuntoControl(
            clave="p06",
            etiqueta="¿Los extintores están visibles y con acceso libre?",
            etiqueta_ko="소화기 위치가 확보되어 있고 접근에 장애물이 없는가?",
            categoria="화재 / Incendio",
        ),
        PuntoControl(
            clave="p07",
            etiqueta="¿La presión y condición física de los extintores son adecuadas?",
            etiqueta_ko="소화기 압력 및 외관 상태가 정상인가?",
            categoria="화재 / Incendio",
        ),
        PuntoControl(
            clave="p08",
            etiqueta="¿Las salidas y rutas de evacuación están libres de obstáculos?",
            etiqueta_ko="비상구 및 대피통로가 확보되어 있는가?",
            categoria="비상 / Emergencia",
        ),
        PuntoControl(
            clave="p09",
            etiqueta=(
                "¿Los tableros eléctricos están cerrados y sin cables expuestos o "
                "dañados?"
            ),
            etiqueta_ko="전기판넬이 정상적으로 닫혀 있고 파손·노출 배선이 없는가?",
            categoria="전기 / Eléctrico",
        ),
        PuntoControl(
            clave="p10",
            etiqueta=(
                "¿Los contactos, cables y equipos eléctricos están libres de daños "
                "o sobrecalentamiento?"
            ),
            etiqueta_ko="콘센트, 케이블 및 전기설비에 과열·손상 흔적이 없는가?",
            categoria="전기 / Eléctrico",
        ),
        PuntoControl(
            clave="p11",
            etiqueta=(
                "¿La conexión a tierra de los silos y tuberías está instalada y sin "
                "daños?"
            ),
            etiqueta_ko="사일로 및 배관의 접지선이 연결되어 있고 손상이 없는가?",
            categoria="정전기 / Estática",
        ),
        PuntoControl(
            clave="p12",
            etiqueta=(
                "¿El sistema de control de electricidad estática y puesta a tierra "
                "está en buenas condiciones?"
            ),
            etiqueta_ko="정전기 방지 설비 및 접지 연결 상태에 이상이 없는가?",
            categoria="정전기 / Estática",
        ),
        PuntoControl(
            clave="p13",
            etiqueta="¿El cuerpo del silo está libre de grietas, deformaciones o daños?",
            etiqueta_ko="사일로 본체에 균열, 변형 또는 파손이 없는가?",
            categoria="사일로 / Silo",
        ),
        PuntoControl(
            clave="p14",
            etiqueta=(
                "¿Los soportes, pernos y puntos de fijación del silo están firmes y "
                "sin deformaciones?"
            ),
            etiqueta_ko="사일로 지지대, 볼트 및 고정부에 풀림·변형이 없는가?",
            categoria="사일로 / Silo",
        ),
        PuntoControl(
            clave="p15",
            etiqueta=(
                "¿Las entradas y salidas de material del silo están correctamente "
                "cerradas?"
            ),
            etiqueta_ko="원료 투입구 및 배출구가 정상적으로 닫혀 있는가?",
            categoria="사일로 / Silo",
        ),
        PuntoControl(
            clave="p16",
            etiqueta=(
                "¿El nivel de material está dentro del rango normal y sin riesgo de "
                "sobrellenado?"
            ),
            etiqueta_ko="원료 레벨이 정상 범위이며 과충전 위험이 없는가?",
            categoria="사일로 / Silo",
        ),
        PuntoControl(
            clave="p17",
            etiqueta=(
                "¿Las tuberías de transporte de EPS están libres de grietas, daños "
                "o desconexiones?"
            ),
            etiqueta_ko="EPS 이송 배관에 균열, 파손 또는 이탈이 없는가?",
            categoria="배관 / Tubería",
        ),
        PuntoControl(
            clave="p18",
            etiqueta="¿Las conexiones de las tuberías están libres de fugas de EPS?",
            etiqueta_ko="배관 연결부에서 EPS 원료가 누출되지 않는가?",
            categoria="배관 / Tubería",
        ),
        PuntoControl(
            clave="p19",
            etiqueta="¿Las válvulas y conexiones están en posición correcta y sin daños?",
            etiqueta_ko="밸브 및 연결부가 정상 위치에 있고 손상이 없는가?",
            categoria="배관 / Tubería",
        ),
        PuntoControl(
            clave="p20",
            etiqueta="¿El soplador funciona sin ruido o vibración anormal?",
            etiqueta_ko="Blower 작동 시 비정상적인 소음·진동이 없는가?",
            categoria="Blower / Soplador",
        ),
        PuntoControl(
            clave="p21",
            etiqueta=(
                "¿El motor del soplador está libre de sobrecalentamiento u olor a "
                "quemado?"
            ),
            etiqueta_ko="Blower 모터 및 주변에 과열 또는 타는 냄새가 없는가?",
            categoria="Blower / Soplador",
        ),
        PuntoControl(
            clave="p22",
            etiqueta=(
                "¿El sistema de ventilación del cuarto de silos funciona "
                "correctamente?"
            ),
            etiqueta_ko="사일로실 환기설비가 정상 작동하는가?",
            categoria="환기 / Ventilación",
        ),
        PuntoControl(
            clave="p23",
            etiqueta=(
                "¿Las rejillas y ductos de ventilación están libres de "
                "obstrucciones?"
            ),
            etiqueta_ko="환기구 및 덕트가 막혀 있지 않은가?",
            categoria="환기 / Ventilación",
        ),
        PuntoControl(
            clave="p24",
            etiqueta=(
                "¿El área está libre de acumulación excesiva de polvo o residuos de "
                "EPS?"
            ),
            etiqueta_ko="EPS 분진 및 잔재물이 과도하게 쌓여 있지 않은가?",
            categoria="청소 / Limpieza",
        ),
        PuntoControl(
            clave="p25",
            etiqueta="¿El piso y los equipos están libres de fugas o derrames de EPS?",
            etiqueta_ko="EPS 원료가 바닥 또는 설비 주변으로 누출되지 않는가?",
            categoria="누출 / Fugas",
        ),
        PuntoControl(
            clave="p26",
            etiqueta="¿Los manómetros indican valores dentro del rango normal?",
            etiqueta_ko="압력계가 정상 범위를 표시하고 있는가?",
            categoria="압력 / Presión",
        ),
        PuntoControl(
            clave="p27",
            etiqueta=(
                "¿Las tuberías y válvulas de presión están libres de fugas o "
                "anomalías?"
            ),
            etiqueta_ko="압력 관련 배관·밸브에서 누설이나 이상이 없는가?",
            categoria="압력 / Presión",
        ),
        PuntoControl(
            clave="p28",
            etiqueta=(
                "¿El botón de paro de emergencia (E-STOP) está accesible y sin "
                "daños?"
            ),
            etiqueta_ko="비상정지(E-STOP) 버튼의 접근이 가능하고 파손이 없는가?",
            categoria="비상 / Emergencia",
        ),
        PuntoControl(
            clave="p29",
            etiqueta=(
                "¿La iluminación y señalización de emergencia están en buenas "
                "condiciones?"
            ),
            etiqueta_ko="비상조명 및 비상표지가 정상 상태인가?",
            categoria="비상 / Emergencia",
        ),
        PuntoControl(
            clave="p30",
            etiqueta=(
                "¿El personal utiliza el equipo de protección personal (EPP) "
                "requerido?"
            ),
            etiqueta_ko="작업자가 지정된 개인보호구(PPE)를 착용하고 있는가?",
            categoria="PPE / EPP",
        ),
        ),
    ),
    "tableros": DefinicionChecklist(
        clave="tableros",
        titulo="Checklist diario de seguridad – Tableros eléctricos",
        titulo_ko="전기 판넬 안전 일일 체크시트",
        hoja="Tableros electricos",
        subtitulo=None,
        estilo_valores="si_no",
        encabezado=(
            CampoFormato(clave="planta", etiqueta="Planta", etiqueta_ko="공장"),
            CampoFormato(clave="area", etiqueta="Área", etiqueta_ko="구역"),
            CampoFormato(
                clave="tablero", etiqueta="No. de tablero", etiqueta_ko="판넬 번호",
            ),
            CampoFormato(
            clave="turno",
            etiqueta="Turno",
            etiqueta_ko="근무조",
            tipo="opcion",
            opciones=("Día", "Noche"),
        ),
            CampoFormato(clave="inspector", etiqueta="Inspector", etiqueta_ko="점검자"),
        ),
        # Cada tablero se revisa por separado, así que en un día hay tantas
        # inspecciones como tableros y turnos.
        clave_unicidad=("tablero", "turno"),
        secciones=(
            SeccionFormato(
                clave="temperatura",
                titulo="Registro de temperatura del tablero",
                titulo_ko="판넬 온도 기록",
                campos=(
                    CampoFormato(
                        clave="hora", etiqueta="Hora de medición",
                        etiqueta_ko="측정시간", tipo="hora",
                    ),
                    CampoFormato(
                        clave="ambiente", etiqueta="Temp. ambiente",
                        etiqueta_ko="주변온도", tipo="numero", unidad="°C",
                    ),
                    CampoFormato(
                        clave="tablero", etiqueta="Temp. del tablero",
                        etiqueta_ko="판넬온도", tipo="numero", unidad="°C",
                    ),
                    CampoFormato(
                        clave="maxima", etiqueta="Temp. máxima",
                        etiqueta_ko="최고온도", tipo="numero", unidad="°C",
                    ),
                    CampoFormato(
                        clave="diferencia", etiqueta="Diferencia ΔT",
                        etiqueta_ko="온도차", tipo="numero", unidad="°C",
                    ),
                    CampoFormato(
                        clave="equipo", etiqueta="Equipo de medición",
                        etiqueta_ko="측정장비", tipo="opcion",
                        opciones=("IR", "Cámara termográfica"),
                    ),
                    CampoFormato(
                        clave="resultado", etiqueta="Resultado",
                        etiqueta_ko="판정", tipo="opcion",
                        opciones=("Normal", "Anormal"),
                    ),
                    CampoFormato(
                        clave="requiere_accion", etiqueta="Requiere acción",
                        etiqueta_ko="조치 필요", tipo="opcion",
                        opciones=("Sí", "No"),
                    ),
                ),
            ),
            SeccionFormato(
                clave="anomalia",
                titulo="Acción en caso de anomalía",
                titulo_ko="이상 발견 시 조치",
                solo_con_hallazgos=True,
                campos=(
                    CampoFormato(
                        clave="accion", etiqueta="Acción tomada",
                        etiqueta_ko="조치 내용", tipo="texto_largo",
                    ),
                ),
            ),
        ),
        nota=(
            "IMPORTANTE: en caso de marcar \u201cNo\u201d o detectar temperatura "
            "anormal o puntos calientes, reportar de inmediato a Seguridad y "
            "Mantenimiento, y restringir el acceso cuando sea necesario."
        ),
        nota_ko=(
            "중요: \u201cNo\u201d 항목 또는 비정상 온도/Hot Spot 발견 시 즉시 "
            "안전·유지보수 담당자에게 보고하고 필요한 경우 접근을 통제하십시오."
        ),
        puntos=(
        PuntoControl(
            clave="p01",
            etiqueta="¿El tablero está completamente cerrado y asegurado?",
            etiqueta_ko="판넬 문이 완전히 닫혀 있고 잠금 상태인가?",
        ),
        PuntoControl(
            clave="p02",
            etiqueta=(
                "¿El área frente al tablero está libre de materiales, cajas u "
                "obstáculos?"
            ),
            etiqueta_ko="판넬 앞에 자재, 박스 등 장애물이 없는가?",
        ),
        PuntoControl(
            clave="p03",
            etiqueta="¿No hay agua, humedad o fugas cerca del tablero?",
            etiqueta_ko="판넬 주변에 물, 습기 또는 누수가 없는가?",
        ),
        PuntoControl(
            clave="p04",
            etiqueta="¿No hay cables expuestos o dañados?",
            etiqueta_ko="전선이나 케이블의 노출 또는 손상이 없는가?",
        ),
        PuntoControl(
            clave="p05",
            etiqueta="¿No se detecta olor a quemado u otro olor anormal?",
            etiqueta_ko="판넬에서 타는 냄새나 이상한 냄새가 없는가?",
        ),
        PuntoControl(
            clave="p06",
            etiqueta="¿No hay ruidos o vibraciones anormales?",
            etiqueta_ko="판넬에서 비정상적인 소음이나 진동이 없는가?",
        ),
        PuntoControl(
            clave="p07",
            etiqueta="¿Se midió la temperatura de la superficie exterior del tablero?",
            etiqueta_ko="판넬 외부 표면 온도를 측정하였는가?",
            medicion="°C",
        ),
        PuntoControl(
            clave="p08",
            etiqueta=(
                "¿Se verificaron puntos calientes con cámara termográfica o "
                "termómetro infrarrojo?"
            ),
            etiqueta_ko="열화상 카메라 또는 비접촉 온도계로 주요부의 이상 발열(Hot Spot)을 확인하였는가?",
            medicion="Máx. °C",
        ),
        PuntoControl(
            clave="p09",
            etiqueta=(
                "¿No existe un aumento significativo de temperatura ni puntos "
                "calientes anormales?"
            ),
            etiqueta_ko="전일 대비 급격한 온도 상승 또는 비정상적인 Hot Spot이 없는가?",
            medicion="ΔT °C",
        ),
        PuntoControl(
            clave="p10",
            etiqueta="¿Los interruptores y breakers están en buenas condiciones?",
            etiqueta_ko="차단기 및 스위치에 파손이나 이상이 없는가?",
        ),
        PuntoControl(
            clave="p11",
            etiqueta="¿Las etiquetas de riesgo eléctrico y voltaje están visibles?",
            etiqueta_ko="판넬의 전기 위험 경고 및 전압 표시가 잘 보이는가?",
        ),
        PuntoControl(
            clave="p12",
            etiqueta="¿El tablero y los circuitos están correctamente identificados?",
            etiqueta_ko="판넬 및 회로 식별표가 명확하게 표시되어 있는가?",
        ),
        PuntoControl(
            clave="p13",
            etiqueta="¿La conexión a tierra no presenta anomalías visibles?",
            etiqueta_ko="접지 연결에 외관상 이상이 없는가?",
        ),
        PuntoControl(
            clave="p14",
            etiqueta=(
                "¿El área alrededor del tablero está libre de materiales "
                "inflamables?"
            ),
            etiqueta_ko="판넬 주변에 가연성 물질이 없는가?",
        ),
        PuntoControl(
            clave="p15",
            etiqueta=(
                "¿Se mantiene libre el espacio de seguridad y acceso frente al "
                "tablero?"
            ),
            etiqueta_ko="판넬 앞 안전거리 및 접근 공간이 확보되어 있는가?",
        ),
        PuntoControl(
            clave="p16",
            etiqueta=(
                "¿Las cubiertas, tornillos y protecciones están correctamente "
                "instalados?"
            ),
            etiqueta_ko="판넬 커버, 볼트 및 보호부품이 정상적으로 설치되어 있는가?",
        ),
        PuntoControl(
            clave="p17",
            etiqueta="¿No existen conexiones o cableados provisionales no autorizados?",
            etiqueta_ko="승인되지 않은 임시 배선이나 연결이 없는가?",
        ),
        PuntoControl(
            clave="p18",
            etiqueta=(
                "¿El exterior y el área alrededor del tablero están libres de "
                "telarañas, polvo y materiales extraños?"
            ),
            etiqueta_ko="판넬 외부 및 주변의 거미줄, 먼지, 이물질이 제거되어 청결한가?",
        ),
        ),
    ),
}

VALORES_CHECKLIST: Final[frozenset[str]] = frozenset({"ok", "no_ok"})

# Cómo se rotula cada valor en la hoja de Excel.
ETIQUETAS_VALOR_CHECKLIST: Final[dict[str, str]] = {
    "ok": "OK",
    "no_ok": "NO OK",
}

# Los formatos por inspección rotulan las mismas dos respuestas como SÍ / NO.
ETIQUETAS_VALOR_SI_NO: Final[dict[str, str]] = {
    "ok": "SÍ",
    "no_ok": "NO",
}


def definicion_checklist(clave: str) -> DefinicionChecklist | None:
    """Devuelve la definición de un control, o ``None`` si no existe."""
    return CONTROLES_CHECKLIST.get(clave)


# --- Pláticas diarias de seguridad -----------------------------------------
#
# Las áreas de esta hoja NO son las de ``core/constants.py``: aquellas son las
# del cuestionario y estas son las columnas del formato de pláticas, con la
# abreviatura que usa el personal de piso. Se mantienen separadas a propósito.

AREAS_PLATICAS: Final[tuple[PuntoControl, ...]] = (
    PuntoControl("assy", "ASSY"),
    PuntoControl("eps", "EPS"),
    PuntoControl("almacen", "ALMACEN"),
    PuntoControl("mtto", "MTTO"),
    PuntoControl("embarque", "EMBARQUE"),
    PuntoControl("ventas", "VENTAS"),
)

CLAVES_AREAS_PLATICAS: Final[frozenset[str]] = frozenset(
    area.clave for area in AREAS_PLATICAS
)

TITULO_PLATICAS: Final[str] = "PLATICAS DIARIAS DE SEGURIDAD"

# Cuántas fotos de evidencia admite un punto en NO OK o una plática. El tope
# existe para que una petición con varias fotos no crezca sin control.
MAX_FOTOS: Final[int] = 4
