'use client';

import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { ErrorDeApi, guardarMetas, obtenerMetas } from '@/lib/api';
import type { MetaArea } from '@/lib/types';

interface ModalMetasProps {
  abierto: boolean;
  onCerrar: () => void;
  onGuardado: () => void;
}

/**
 * Captura del headcount por área.
 *
 * Es el denominador del KPI de participación: sin estas metas, el dashboard
 * muestra el conteo absoluto y oculta el porcentaje.
 */
export function ModalMetas({ abierto, onCerrar, onGuardado }: ModalMetasProps) {
  const { mostrarToast } = useToast();

  const [metas, setMetas] = useState<MetaArea[]>([]);
  const [valores, setValores] = useState<Record<string, string>>({});
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!abierto) {
      return;
    }

    let cancelado = false;
    setCargando(true);
    setError('');
    setGuardando(false);

    obtenerMetas()
      .then((datos) => {
        if (cancelado) {
          return;
        }
        setMetas(datos);
        setValores(
          Object.fromEntries(
            datos.map((meta) => [meta.area, meta.headcount?.toString() ?? '']),
          ),
        );
      })
      .catch((problema) => {
        if (!cancelado) {
          setError(
            problema instanceof ErrorDeApi
              ? problema.message
              : 'No se pudieron cargar las metas.',
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
  }, [abierto]);

  async function guardar() {
    setError('');
    setGuardando(true);

    // Las áreas que se dejan en blanco no se envían: quedan sin meta y su
    // porcentaje de participación se oculta, en vez de contarse como cero.
    const aEnviar = Object.entries(valores)
      .filter(([, valor]) => valor.trim() !== '')
      .map(([area, valor]) => ({ area, headcount: Number(valor) }));

    const invalidos = aEnviar.filter(
      (meta) => !Number.isInteger(meta.headcount) || meta.headcount < 0,
    );

    if (invalidos.length > 0) {
      setError('El headcount debe ser un número entero mayor o igual a cero.');
      setGuardando(false);
      return;
    }

    try {
      await guardarMetas(aEnviar);
      mostrarToast('Metas guardadas.', 'exito');
      onGuardado();
      onCerrar();
    } catch (problema) {
      setError(
        problema instanceof ErrorDeApi
          ? problema.message
          : 'No se pudieron guardar las metas.',
      );
      setGuardando(false);
    }
  }

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      titulo="Metas de participación por área"
      descripcion="Cuántas personas hay en cada área. Es el denominador del nivel de participación."
      pie={
        <>
          {error && (
            <p role="alert" className="mr-auto text-sm text-error">
              {error}
            </p>
          )}
          <Button variante="fantasma" onClick={onCerrar}>
            Cancelar
          </Button>
          <Button onClick={() => void guardar()} cargando={guardando}>
            Guardar metas
          </Button>
        </>
      }
    >
      {cargando ? (
        <p className="py-6 text-center text-texto-suave">Cargando metas…</p>
      ) : (
        <div className="flex flex-col gap-3">
          {metas.map((meta) => (
            <div key={meta.area} className="flex items-center gap-4">
              <label
                htmlFor={`meta-${meta.area}`}
                className="w-40 shrink-0 text-sm text-texto"
              >
                {meta.label}
              </label>
              <input
                id={`meta-${meta.area}`}
                type="number"
                min={0}
                inputMode="numeric"
                value={valores[meta.area] ?? ''}
                onChange={(evento) =>
                  setValores((previos) => ({
                    ...previos,
                    [meta.area]: evento.target.value,
                  }))
                }
                placeholder="Sin capturar"
                className="h-10 w-32 rounded-md border border-borde bg-fondo px-3 text-sm text-texto placeholder:text-texto-tenue focus:border-primario"
              />
              <span className="text-sm text-texto-tenue">personas</span>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
