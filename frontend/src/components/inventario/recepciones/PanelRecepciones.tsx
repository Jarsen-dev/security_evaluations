'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  BloqueDocumento,
  type Documento,
  type PartidaBorrador,
  type ResultadoCodigo,
} from '@/components/inventario/recepciones/BloqueDocumento';
import { ModalQrCaptura } from '@/components/inventario/recepciones/ModalQrCaptura';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';
import { VisorImagen } from '@/components/ui/VisorImagen';
import {
  ErrorDeApi,
  guardarRecepcion,
  insumosPorCodigo,
  procesarFotoDeSesion,
  procesarFotoRecepcion,
  urlFotoRecepcion,
} from '@/lib/api';
import { bilingue, useTraduccion } from '@/lib/i18n';
import { REDUCCION_DOCUMENTO, reducirImagen } from '@/lib/imagen';
import { idUnico } from '@/lib/navegador';
import { useSesion } from '@/lib/sesion';
import type { CandidatoInsumo, RecepcionPayload, ResultadoOcr } from '@/lib/types';

/** Las tres fases por las que pasa una captura. */
type Fase = 'captura' | 'procesando' | 'revision';

/** Espera antes de saltar al primer campo faltante, ya pintada la pantalla. */
const MS_ENFOQUE = 300;

function partidaVacia(): PartidaBorrador {
  return {
    idLocal: idUnico(),
    codigo: '',
    cantidad: '',
    descripcion: '',
    candidatos: [],
    insumoId: null,
    noRegistrado: false,
  };
}

/** Convierte lo que devolvió la extracción en un documento editable. */
function documentoDesdeOcr(resultado: ResultadoOcr): Documento {
  const items = resultado.items.map((item) => {
    const candidatos = item.candidatos ?? [];
    const elegido = item.insumo_id ?? null;

    return {
      ...partidaVacia(),
      codigo: item.codigo ?? '',
      cantidad:
        item.cantidad === null || item.cantidad === undefined
          ? ''
          : String(item.cantidad),
      candidatos,
      insumoId: elegido,
      // Si el servidor ya resolvió cuál es, se muestra la descripción del
      // catálogo; si no, la que leyó del papel, que es la pista con la que el
      // operador va a elegir.
      descripcion:
        candidatos.find((candidato) => candidato.id === elegido)?.descripcion ??
        item.descripcion ??
        '',
      noRegistrado: (item.codigo ?? '') !== '' && candidatos.length === 0,
    };
  });

  return {
    idLocal: idUnico(),
    proveedor: resultado.proveedor ?? '',
    folio: resultado.folio ?? '',
    fecha: resultado.fecha ?? '',
    tipo_documento: resultado.tipo_documento,
    tipo_conocido: resultado.tipo_conocido,
    tipoNombre: resultado.tipo_nombre ?? '',
    ocr_ok: resultado.ocr_ok,
    ocr_raw: resultado.ocr_raw,
    advertencias: resultado.advertencias,
    nuevoFormato: '',
    // Aunque la IA no haya leído ninguna partida, siempre hay un renglón que
    // llenar: si no, el operador se queda mirando una lista vacía.
    items: items.length > 0 ? items : [partidaVacia()],
  };
}

/**
 * Captura de recepciones por foto.
 *
 * Máquina de estados de tres fases: `captura → procesando → revision`. Lo que
 * hace usable la corrección es la fase de revisión **lado a lado**: la foto se
 * queda fija a la izquierda mientras se corrigen los campos a la derecha, así
 * que nadie tiene que volver por la hoja física.
 */
export function PanelRecepciones() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();
  const { puede } = useSesion();

  const puedeEditar = puede('inventario', 'editar');

  const [fase, setFase] = useState<Fase>('captura');
  const [fotoId, setFotoId] = useState<string | null>(null);
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [errores, setErrores] = useState<Record<string, Record<string, string>>>({});
  const [guardando, setGuardando] = useState(false);
  const [qrAbierto, setQrAbierto] = useState(false);
  const [avisoIa, setAvisoIa] = useState('');

  const entrada = useRef<HTMLInputElement>(null);
  const formulario = useRef<HTMLDivElement>(null);

  // Caché de los códigos ya consultados: en una remisión de veinte partidas
  // el mismo código se repite y no tiene caso volver a preguntar. Solo se
  // cachean las respuestas buenas: un fallo no es un dato.
  const catalogo = useRef(new Map<string, CandidatoInsumo[]>());

  const buscarCodigo = useCallback(async (codigo: string): Promise<ResultadoCodigo> => {
    const clave = codigo.trim().toLowerCase();
    const enCache = catalogo.current.get(clave);
    if (enCache !== undefined) {
      return { estado: 'ok', candidatos: enCache };
    }

    try {
      const insumos = await insumosPorCodigo(codigo.trim());
      const candidatos: CandidatoInsumo[] = insumos.map((insumo) => ({
        id: insumo.id,
        descripcion: insumo.descripcion,
        unidad_medida: insumo.unidad_medida,
        piezas_por_empaque: insumo.piezas_por_empaque,
      }));
      catalogo.current.set(clave, candidatos);
      return { estado: 'ok', candidatos };
    } catch {
      // Sin catálogo no se puede afirmar que el código no existe: quien llama
      // lo deja pasar y el backend decide al guardar. Devolver una lista
      // vacía marcaría en rojo códigos perfectamente válidos.
      return { estado: 'fallo' };
    }
  }, []);

  function recibirResultado(resultado: ResultadoOcr) {
    // El servidor ya resolvió los códigos del documento: se siembra la caché
    // con eso en vez de volver a preguntarlos uno por uno.
    for (const item of resultado.items) {
      if (typeof item.codigo === 'string' && item.codigo.trim() !== '') {
        catalogo.current.set(item.codigo.trim().toLowerCase(), item.candidatos ?? []);
      }
    }

    setFotoId(resultado.foto_id);
    setDocumentos([documentoDesdeOcr(resultado)]);
    setErrores({});
    setAvisoIa(resultado.ocr_ok ? '' : (resultado.error ?? t('recepciones.avisoManual')));
    setFase('revision');
  }

  async function procesarArchivo(archivo: File) {
    if (!archivo.type.startsWith('image/')) {
      mostrarToast(t('recepciones.fotoInvalida'), 'error');
      return;
    }

    setFase('procesando');

    try {
      const reducida = await reducirImagen(archivo, REDUCCION_DOCUMENTO);
      recibirResultado(await procesarFotoRecepcion(reducida));
    } catch (error: unknown) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('recepciones.falloProcesar'),
        'error',
      );
      setFase('captura');
    }
  }

  async function procesarDesdeCelular(sesionId: string) {
    setQrAbierto(false);
    setFase('procesando');

    try {
      recibirResultado(await procesarFotoDeSesion(sesionId));
    } catch (error: unknown) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('recepciones.falloProcesar'),
        'error',
      );
      setFase('captura');
    }
  }

  // Al entrar a revisión, el cursor salta al primer campo que la IA no leyó.
  // Con una remisión larga, buscarlo a mano es justo el trabajo que este
  // módulo intenta ahorrar.
  useEffect(() => {
    if (fase !== 'revision' || formulario.current === null) {
      return;
    }

    const temporizador = setTimeout(() => {
      const campo = formulario.current?.querySelector<HTMLInputElement>(
        'input.border-alerta',
      );
      campo?.focus();
      campo?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }, MS_ENFOQUE);

    return () => clearTimeout(temporizador);
  }, [fase]);

  function validar(): boolean {
    const encontrados: Record<string, Record<string, string>> = {};

    for (const documento of documentos) {
      const problemas: Record<string, string> = {};

      if (documento.ocr_ok && !documento.tipo_conocido && documento.nuevoFormato.trim() === '') {
        problemas.nuevoFormato = t('recepciones.faltaFormato');
      }

      documento.items.forEach((partida, indice) => {
        if (partida.codigo.trim() === '') {
          problemas[`items[${indice}].codigo`] = t('recepciones.faltaCodigo');
        }
        if (!/^\d+$/.test(partida.cantidad.trim()) || Number(partida.cantidad) <= 0) {
          problemas[`items[${indice}].cantidad`] = t('recepciones.faltaCantidad');
        }
        // Con varias descripciones para el mismo código, elegir es lo único
        // que puede hacer el operador y el servidor no puede adivinar. Un
        // código inexistente NO se bloquea aquí a propósito: eso se arregla en
        // Catálogo, y el servidor responde con todos los que falten de una vez.
        if (partida.candidatos.length > 1 && partida.insumoId === null) {
          problemas[`items[${indice}].insumo`] = t('recepciones.faltaInsumo');
        }
      });

      if (documento.items.length === 0) {
        problemas.items = t('recepciones.sinPartidas');
      }

      if (Object.keys(problemas).length > 0) {
        encontrados[documento.idLocal] = problemas;
      }
    }

    setErrores(encontrados);
    return Object.keys(encontrados).length === 0;
  }

  function aPayload(documento: Documento): RecepcionPayload {
    const vacio = (valor: string) => valor.trim() || null;

    return {
      foto_id: fotoId,
      proveedor: vacio(documento.proveedor),
      folio: vacio(documento.folio),
      fecha: vacio(documento.fecha),
      tipo_documento: documento.tipo_documento,
      ocr_ok: documento.ocr_ok,
      ocr_raw: documento.ocr_raw,
      advertencias: documento.advertencias,
      nuevo_formato: vacio(documento.nuevoFormato),
      items: documento.items.map((partida) => ({
        codigo: partida.codigo.trim(),
        cantidad: Number(partida.cantidad),
        insumo_id: partida.insumoId,
        // La del papel, no la del catálogo: es lo que alimenta los ejemplos
        // del OCR y lo que le enseña a leer, no a inventar.
        descripcion: partida.descripcion.trim() || null,
      })),
    };
  }

  async function guardar() {
    if (!validar()) {
      return;
    }

    setGuardando(true);
    let guardados = 0;

    try {
      // Se guardan de uno en uno. Si el tercero falla, los dos primeros YA
      // están en la base: hay que recortarlos del formulario o el reintento
      // los duplicaría.
      const avisos: string[] = [];

      for (const documento of documentos) {
        const guardada = await guardarRecepcion(aPayload(documento));
        guardados += 1;
        // El backend aprende del documento después de guardarlo, y si no
        // pudo lo dice aquí. Callarlo dejaba al operador creyendo que su
        // formato había quedado registrado.
        if (guardada.aviso) {
          avisos.push(guardada.aviso);
        }
      }

      mostrarToast(t('recepciones.guardado'), 'exito');
      for (const aviso of avisos) {
        mostrarToast(aviso, 'info');
      }
      reiniciar();
    } catch (error: unknown) {
      const mensaje =
        error instanceof ErrorDeApi ? error.message : t('recepciones.falloGuardar');

      if (guardados > 0) {
        setDocumentos((previos) => previos.slice(guardados));
        mostrarToast(
          t('recepciones.yaGuardados', { total: guardados, error: mensaje }),
          'error',
        );
      } else {
        mostrarToast(mensaje, 'error');
      }
    } finally {
      setGuardando(false);
    }
  }

  function reiniciar() {
    setFase('captura');
    setFotoId(null);
    setDocumentos([]);
    setErrores({});
    setAvisoIa('');
    catalogo.current.clear();
  }

  if (fase === 'procesando') {
    return (
      <Card className="flex flex-col items-center gap-4 py-16 text-center">
        <span
          className="h-10 w-10 animate-spin rounded-full border-4 border-borde border-t-primario"
          aria-hidden
        />
        <p className="text-lg font-medium text-texto">{bilingue(t('recepciones.procesando'))}</p>
        {/* Expectativa honesta, sin barra de progreso falsa: no hay forma de
            saber cuánto falta. */}
        <p className="text-sm text-texto-suave">{bilingue(t('recepciones.procesandoDetalle'))}</p>
      </Card>
    );
  }

  if (fase === 'captura') {
    return (
      <>
        <Card className="flex flex-col items-center gap-6 py-14 text-center">
          <div className="max-w-xl">
            <h2 className="text-lg font-semibold text-texto">
              {bilingue(t('recepciones.titulo'))}
            </h2>
            <p className="mt-2 text-sm text-texto-suave">
              {bilingue(t('recepciones.descripcion'))}
            </p>
          </div>

          <div className="flex flex-wrap justify-center gap-3">
            <Button
              tamano="lg"
              disabled={!puedeEditar}
              onClick={() => entrada.current?.click()}
            >
              {bilingue(t('recepciones.subirFoto'))}
            </Button>
            <Button
              variante="secundario"
              tamano="lg"
              disabled={!puedeEditar}
              onClick={() => setQrAbierto(true)}
            >
              {bilingue(t('recepciones.conCelular'))}
            </Button>
          </div>

          <input
            ref={entrada}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(evento) => {
              const archivo = evento.target.files?.[0];
              evento.target.value = '';
              if (archivo) void procesarArchivo(archivo);
            }}
          />
        </Card>

        <ModalQrCaptura
          abierto={qrAbierto}
          onCerrar={() => setQrAbierto(false)}
          onFotoLista={(sesionId) => void procesarDesdeCelular(sesionId)}
        />
      </>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* La foto se queda a la vista mientras se corrige: es lo que evita
          tener que volver por el papel. */}
      <div className="lg:sticky lg:top-6 lg:self-start">
        <Card className="overflow-hidden p-0">
          <div className="border-b border-borde px-4 py-2 text-sm text-texto-suave">
            {bilingue(t('recepciones.revisaLaFoto'))}
          </div>
          {fotoId !== null && (
            // La remisión llega como la tomó el operador —de lado, o con la
            // letra demasiado chica—, así que se ve en el visor: gira, acerca
            // y se arrastra sin salir de la pantalla de captura.
            <VisorImagen
              src={urlFotoRecepcion(fotoId)}
              alt={t('recepciones.revisaLaFoto')}
              className="h-[60vh] w-full lg:h-[70vh]"
            />
          )}
        </Card>
      </div>

      <div ref={formulario} className="flex flex-col gap-4">
        {avisoIa !== '' && (
          <p
            role="alert"
            className="rounded-tarjeta border border-alerta bg-alerta-suave px-4 py-3 text-sm text-texto"
          >
            {avisoIa}
          </p>
        )}

        {documentos.map((documento, indice) => (
          <BloqueDocumento
            key={documento.idLocal}
            documento={documento}
            numero={indice + 1}
            total={documentos.length}
            errores={errores[documento.idLocal] ?? {}}
            onBuscarCodigo={buscarCodigo}
            onCambiar={(siguiente) =>
              setDocumentos((previos) =>
                previos.map((otro) =>
                  otro.idLocal === siguiente.idLocal ? siguiente : otro,
                ),
              )
            }
            onQuitar={() =>
              setDocumentos((previos) =>
                previos.filter((otro) => otro.idLocal !== documento.idLocal),
              )
            }
          />
        ))}

        {/* Una hoja puede traer varias remisiones impresas juntas; todas
            comparten la misma foto. */}
        <Button
          variante="secundario"
          onClick={() =>
            setDocumentos((previos) => [
              ...previos,
              {
                ...documentoDesdeOcr({
                  foto_id: fotoId ?? '',
                  ocr_ok: true,
                  tipo_documento: previos[0]?.tipo_documento ?? 'desconocido',
                  tipo_conocido: previos[0]?.tipo_conocido ?? false,
                  tipo_nombre: previos[0]?.tipoNombre || null,
                  proveedor: null,
                  folio: null,
                  fecha: null,
                  items: [],
                  advertencias: [],
                  ocr_raw: null,
                  error: null,
                }),
              },
            ])
          }
        >
          {bilingue(t('recepciones.otroDocumento'))}
        </Button>

        <div className="flex flex-wrap gap-3 border-t border-borde pt-4">
          <Button onClick={() => void guardar()} cargando={guardando} disabled={!puedeEditar}>
            {bilingue(documentos.length > 1
              ? t('recepciones.guardarTodo', { total: documentos.length })
              : t('recepciones.guardar'))}
          </Button>
          <Button variante="fantasma" onClick={reiniciar} disabled={guardando}>
            {bilingue(t('recepciones.cancelar'))}
          </Button>
        </div>
      </div>
    </div>
  );
}
