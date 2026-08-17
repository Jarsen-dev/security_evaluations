'use client';

import { useEffect, useRef, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import type { CuestionarioResumen } from '@/lib/types';

interface TarjetaCuestionarioProps {
  cuestionario: CuestionarioResumen;
  onEditar: () => void;
  onVerQR: () => void;
  onCopiarLiga: () => void;
  onImprimir: () => void;
  imprimiendo: boolean;
  onDuplicar: () => void;
  onAlternarActivo: () => void;
  onEliminar: () => void;
}

export function TarjetaCuestionario({
  cuestionario,
  onEditar,
  onVerQR,
  onCopiarLiga,
  onImprimir,
  imprimiendo,
  onDuplicar,
  onAlternarActivo,
  onEliminar,
}: TarjetaCuestionarioProps) {
  const [menuAbierto, setMenuAbierto] = useState(false);
  const contenedorMenu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuAbierto) {
      return;
    }

    function alHacerClicFuera(evento: MouseEvent) {
      if (
        contenedorMenu.current &&
        !contenedorMenu.current.contains(evento.target as Node)
      ) {
        setMenuAbierto(false);
      }
    }

    function alPresionarEscape(evento: KeyboardEvent) {
      if (evento.key === 'Escape') {
        setMenuAbierto(false);
      }
    }

    document.addEventListener('mousedown', alHacerClicFuera);
    document.addEventListener('keydown', alPresionarEscape);

    return () => {
      document.removeEventListener('mousedown', alHacerClicFuera);
      document.removeEventListener('keydown', alPresionarEscape);
    };
  }, [menuAbierto]);

  function ejecutar(accion: () => void) {
    setMenuAbierto(false);
    accion();
  }

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate font-medium text-texto" title={cuestionario.nombre}>
            {cuestionario.nombre}
          </h2>
          {cuestionario.descripcion && (
            <p className="mt-1 line-clamp-2 text-sm text-texto-suave">
              {cuestionario.descripcion}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <Badge tono={cuestionario.activo ? 'exito' : 'neutro'}>
            {cuestionario.activo ? 'Activo' : 'Inactivo'}
          </Badge>

          <div className="relative" ref={contenedorMenu}>
            <Button
              variante="fantasma"
              tamano="sm"
              onClick={() => setMenuAbierto((previo) => !previo)}
              aria-haspopup="menu"
              aria-expanded={menuAbierto}
              aria-label={`Más acciones para ${cuestionario.nombre}`}
            >
              ⋮
            </Button>

            {menuAbierto && (
              <div
                role="menu"
                className="absolute right-0 z-20 mt-1 w-56 overflow-hidden rounded-md border border-borde bg-fondo-elevado py-1 shadow-lg"
              >
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => ejecutar(onDuplicar)}
                  className="block w-full px-4 py-2 text-left text-sm text-texto hover:bg-fondo-sutil"
                >
                  Duplicar
                </button>

                <button
                  type="button"
                  role="menuitem"
                  onClick={() => ejecutar(onAlternarActivo)}
                  className="block w-full px-4 py-2 text-left text-sm text-texto hover:bg-fondo-sutil"
                >
                  {cuestionario.activo ? 'Desactivar' : 'Activar'}
                </button>

                <button
                  type="button"
                  role="menuitem"
                  onClick={() => ejecutar(onEliminar)}
                  className="block w-full px-4 py-2 text-left text-sm text-error hover:bg-error-suave"
                >
                  Eliminar
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <dl className="flex gap-6 text-sm">
        <div>
          <dt className="text-texto-tenue">Preguntas</dt>
          <dd className="font-medium text-texto">{cuestionario.total_preguntas}</dd>
        </div>
        <div>
          <dt className="text-texto-tenue">Respuestas</dt>
          <dd className="font-medium text-texto">{cuestionario.total_respuestas}</dd>
        </div>
      </dl>

      <div className="flex flex-wrap items-center gap-2">
        <Button variante="secundario" tamano="sm" onClick={onEditar}>
          Editar
        </Button>

        <Button variante="secundario" tamano="sm" onClick={onVerQR}>
          QR
        </Button>

        <Button
          variante="secundario"
          tamano="sm"
          onClick={onCopiarLiga}
          title="Copia la liga para abrirla desde una PC"
        >
          Liga escritorio
        </Button>

        <Button
          variante="secundario"
          tamano="sm"
          onClick={onImprimir}
          cargando={imprimiendo}
          disabled={cuestionario.total_preguntas === 0}
          title={
            cuestionario.total_preguntas === 0
              ? 'El cuestionario no tiene preguntas que imprimir'
              : 'Descarga el PDF para contestarlo en papel'
          }
        >
          Imprimir
        </Button>

      </div>
    </Card>
  );
}
