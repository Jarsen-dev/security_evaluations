'use client';

import { useEffect, useState } from 'react';

import {
  ConstructorPreguntas,
  nuevoIdLocal,
  preguntaVacia,
} from '@/components/cuestionarios/ConstructorPreguntas';
import { useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import type { ErroresPregunta } from '@/components/cuestionarios/TarjetaPregunta';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import {
  ErrorDeApi,
  actualizarCuestionario,
  crearCuestionario,
  obtenerCuestionario,
} from '@/lib/api';
import type { Cuestionario, PreguntaBorrador, PreguntaPayload } from '@/lib/types';

interface ModalCuestionarioProps {
  abierto: boolean;
  /** Id del cuestionario a editar; `null` significa creación. */
  cuestionarioId: string | null;
  /** Respuestas ya recibidas: si hay, se advierte antes de editar preguntas. */
  totalRespuestas?: number;
  onCerrar: () => void;
  onGuardado: (cuestionario: Cuestionario, esNuevo: boolean) => void;
}

const MIN_OPCIONES = 2;

/** Convierte el detalle que devuelve la API al borrador que edita la UI. */
function aBorrador(cuestionario: Cuestionario): PreguntaBorrador[] {
  return cuestionario.preguntas.map((pregunta) => ({
    idLocal: nuevoIdLocal(),
    id: pregunta.id,
    texto: pregunta.texto,
    puntos: pregunta.puntos,
    opciones: pregunta.opciones.map((opcion) => ({
      idLocal: nuevoIdLocal(),
      id: opcion.id,
      texto: opcion.texto,
      es_correcta: opcion.es_correcta,
    })),
  }));
}

/** Convierte el borrador al cuerpo que espera la API, sin opciones vacías. */
function aPayload(preguntas: PreguntaBorrador[]): PreguntaPayload[] {
  return preguntas.map((pregunta) => ({
    ...(pregunta.id ? { id: pregunta.id } : {}),
    texto: pregunta.texto.trim(),
    puntos: pregunta.puntos,
    opciones: pregunta.opciones
      .filter((opcion) => opcion.texto.trim().length > 0)
      .map((opcion) => ({
        // El id viaja de vuelta cuando la opción ya existe: permite al
        // servidor conservarla en vez de borrarla y recrearla, lo que
        // dejaría en NULL la opción elegida de las respuestas históricas.
        ...(opcion.id ? { id: opcion.id } : {}),
        texto: opcion.texto.trim(),
        es_correcta: opcion.es_correcta,
      })),
  }));
}

/**
 * Valida las reglas de negocio en el cliente antes de enviar.
 *
 * El servidor vuelve a validarlas: esto solo evita un viaje de ida y vuelta
 * y permite señalar el error justo debajo del campo que lo causa.
 */
function validar(
  preguntas: PreguntaBorrador[],
  // La validación vive fuera del componente, así que recibe el traductor en
  // lugar de llamar al hook.
  t: (clave: ClaveTraduccion, valores?: Record<string, string | number>) => string,
): Record<string, ErroresPregunta> {
  const errores: Record<string, ErroresPregunta> = {};

  for (const pregunta of preguntas) {
    const problemas: ErroresPregunta = {};

    if (pregunta.texto.trim().length === 0) {
      problemas.texto = t('modalCuestionario.faltaTexto');
    }

    const conTexto = pregunta.opciones.filter(
      (opcion) => opcion.texto.trim().length > 0,
    );
    const correctas = conTexto.filter((opcion) => opcion.es_correcta);

    if (conTexto.length < MIN_OPCIONES) {
      problemas.opciones = t('modalCuestionario.minimoOpciones', {
        total: MIN_OPCIONES,
      });
    } else if (correctas.length === 0) {
      problemas.opciones = t('modalCuestionario.faltaCorrecta');
    } else if (correctas.length > 1) {
      problemas.opciones = t('modalCuestionario.correctaUnica');
    }

    if (problemas.texto || problemas.opciones) {
      errores[pregunta.idLocal] = problemas;
    }
  }

  return errores;
}

export function ModalCuestionario({
  abierto,
  cuestionarioId,
  totalRespuestas = 0,
  onCerrar,
  onGuardado,
}: ModalCuestionarioProps) {
  const t = useTraduccion();
  const esEdicion = cuestionarioId !== null;

  const [paso, setPaso] = useState<1 | 2>(1);
  const [nombre, setNombre] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [permitirMultiples, setPermitirMultiples] = useState(false);
  const [preguntas, setPreguntas] = useState<PreguntaBorrador[]>([]);
  const [errores, setErrores] = useState<Record<string, ErroresPregunta>>({});
  const [errorGeneral, setErrorGeneral] = useState('');
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);

  // Carga el detalle al abrir en modo edición y limpia el estado al cerrar.
  useEffect(() => {
    if (!abierto) {
      return;
    }

    setPaso(1);
    setErrores({});
    setErrorGeneral('');
    // El modal no se desmonta al cerrarse, así que `guardando` conservaría el
    // `true` del guardado anterior y dejaría el botón deshabilitado al
    // reabrirlo. Se reinicia en cada apertura.
    setGuardando(false);

    if (cuestionarioId === null) {
      setNombre('');
      setDescripcion('');
      setPermitirMultiples(false);
      setPreguntas([preguntaVacia()]);
      return;
    }

    let cancelado = false;
    setCargando(true);

    obtenerCuestionario(cuestionarioId)
      .then((cuestionario) => {
        if (cancelado) {
          return;
        }
        setNombre(cuestionario.nombre);
        setDescripcion(cuestionario.descripcion ?? '');
        setPermitirMultiples(cuestionario.permitir_multiples_intentos);
        setPreguntas(aBorrador(cuestionario));
      })
      .catch((error) => {
        if (!cancelado) {
          setErrorGeneral(
            error instanceof ErrorDeApi
              ? error.message
              : t('modalCuestionario.falloCarga'),
          );
        }
      })
      .finally(() => {
        if (!cancelado) {
          setCargando(false);
        }
      });

    return () => {
      cancelado = true;
    };
  }, [abierto, cuestionarioId, t]);

  async function guardar() {
    setErrorGeneral('');

    if (preguntas.length === 0) {
      setErrorGeneral(t('modalCuestionario.sinPreguntas'));
      return;
    }

    const problemas = validar(preguntas, t);
    if (Object.keys(problemas).length > 0) {
      setErrores(problemas);
      setErrorGeneral(t('modalCuestionario.revisaPreguntas'));
      return;
    }

    setErrores({});
    setGuardando(true);

    try {
      const cuerpo = {
        nombre: nombre.trim(),
        descripcion: descripcion.trim() === '' ? null : descripcion.trim(),
        permitir_multiples_intentos: permitirMultiples,
        preguntas: aPayload(preguntas),
      };

      const guardado = esEdicion
        ? await actualizarCuestionario(cuestionarioId, cuerpo)
        : await crearCuestionario(cuerpo);

      onGuardado(guardado, !esEdicion);
    } catch (error) {
      if (error instanceof ErrorDeApi) {
        // El servidor devuelve un error por cada pregunta con problemas;
        // se muestran todos juntos en lugar de solo el primero.
        setErrorGeneral(
          error.errores && error.errores.length > 0
            ? `${error.message} ${error.errores.map((e) => e.mensaje).join(' ')}`
            : error.message,
        );
      } else {
        setErrorGeneral(t('modalCuestionario.falloGuardado'));
      }
      setGuardando(false);
    }
  }

  const puedeContinuar = nombre.trim().length > 0;

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      ancho="lg"
      titulo={
        esEdicion ? t('modalCuestionario.editar') : t('modalCuestionario.nuevo')
      }
      descripcion={
        paso === 1 ? t('modalCuestionario.paso1') : t('modalCuestionario.paso2')
      }
      pie={
        <>
          {errorGeneral && (
            <p role="alert" className="mr-auto text-sm text-error">
              {errorGeneral}
            </p>
          )}

          {paso === 1 ? (
            <>
              <Button variante="fantasma" onClick={onCerrar}>
                {t('comun.cancelar')}
              </Button>
              <Button onClick={() => setPaso(2)} disabled={!puedeContinuar}>
                {t('modalCuestionario.continuar')}
              </Button>
            </>
          ) : (
            <>
              <Button variante="fantasma" onClick={() => setPaso(1)}>
                {t('modalCuestionario.atras')}
              </Button>
              <Button onClick={guardar} cargando={guardando}>
                {esEdicion
                  ? t('modalCuestionario.guardarCambios')
                  : t('modalCuestionario.crear')}
              </Button>
            </>
          )}
        </>
      }
    >
      {cargando ? (
        <p className="py-8 text-center text-texto-suave">{t('comun.cargando')}</p>
      ) : paso === 1 ? (
        <div className="flex flex-col gap-4">
          <Input
            etiqueta={t('modalCuestionario.nombre')}
            name="nombre"
            value={nombre}
            onChange={(evento) => setNombre(evento.target.value)}
            placeholder={t('modalCuestionario.nombrePlaceholder')}
            autoFocus
            maxLength={200}
          />

          <Textarea
            etiqueta={t('modalCuestionario.descripcion')}
            name="descripcion"
            value={descripcion}
            onChange={(evento) => setDescripcion(evento.target.value)}
            placeholder={t('modalCuestionario.descripcionPlaceholder')}
            maxLength={2000}
          />

          <label className="flex items-start gap-3 rounded-md border border-borde bg-fondo p-3">
            <input
              type="checkbox"
              checked={permitirMultiples}
              onChange={(evento) => setPermitirMultiples(evento.target.checked)}
              className="mt-0.5 h-4 w-4 accent-primario"
            />
            <span>
              <span className="block text-sm font-medium text-texto">
                {t('modalCuestionario.multiples')}
              </span>
              <span className="block text-sm text-texto-suave">
                {t('modalCuestionario.multiplesDetalle')}
              </span>
            </span>
          </label>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {esEdicion && totalRespuestas > 0 && (
            <p className="rounded-md border border-alerta bg-alerta-suave px-3 py-2 text-sm text-texto-suave">
              {t('modalCuestionario.avisoRespuestas')}
            </p>
          )}

          <ConstructorPreguntas
            preguntas={preguntas}
            onCambiar={setPreguntas}
            errores={errores}
          />
        </div>
      )}
    </Modal>
  );
}
