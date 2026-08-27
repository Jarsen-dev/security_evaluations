'use client';

import { useEffect, useState } from 'react';

import { claveEtiqueta, type GrupoOpciones } from '@/components/estudios/opciones';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import type { CatalogoEstudios, Estudio, EstudioPayload, OpcionEstudio } from '@/lib/types';

/** Mismo estilo que `Input`, para que el desplegable no desentone. */
const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario disabled:cursor-not-allowed disabled:opacity-50';

interface FormularioEstudioProps {
  catalogo: CatalogoEstudios;
  /** Cuando viene, el formulario edita ese estudio en lugar de dar de alta. */
  estudio: Estudio | null;
  onGuardar: (datos: EstudioPayload) => Promise<void>;
  onCancelar: () => void;
  guardando: boolean;
}

/** Un formulario en blanco: ninguna opción viene elegida de antemano. */
const VACIO: EstudioPayload = {
  despacho: '',
  estudio: '',
  estudio_ko: null,
  vigencia: '',
  prioridad: '',
  tipo: '',
  estatus: '',
  vencimiento: '',
  fecha_vencimiento: null,
  aprobado: '',
  pagado: '',
  link: null,
};

function desdeEstudio(estudio: Estudio | null): EstudioPayload {
  if (estudio === null) {
    return { ...VACIO };
  }

  return {
    despacho: estudio.despacho,
    estudio: estudio.estudio,
    estudio_ko: estudio.estudio_ko,
    vigencia: estudio.vigencia,
    prioridad: estudio.prioridad,
    tipo: estudio.tipo,
    estatus: estudio.estatus,
    vencimiento: estudio.vencimiento,
    fecha_vencimiento: estudio.fecha_vencimiento,
    aprobado: estudio.aprobado,
    pagado: estudio.pagado,
    link: estudio.link,
  };
}

/**
 * Alta y edición de un estudio.
 *
 * Los campos condicionales siguen la regla del catálogo, no una clave escrita
 * aquí: la fecha aparece con el vencimiento que el backend marca como
 * `vencimiento_con_fecha`, y el link con el estatus `estatus_con_link`.
 */
export function FormularioEstudio({
  catalogo,
  estudio,
  onGuardar,
  onCancelar,
  guardando,
}: FormularioEstudioProps) {
  const t = useTraduccion();
  const [datos, setDatos] = useState<EstudioPayload>(() => desdeEstudio(estudio));

  // Al elegir otro renglón para editar —o al volver al alta— el formulario se
  // vuelve a llenar con lo que corresponde.
  useEffect(() => {
    setDatos(desdeEstudio(estudio));
  }, [estudio]);

  const editando = estudio !== null;
  const pideFecha = datos.vencimiento === catalogo.vencimiento_con_fecha;
  const pideLink = datos.estatus === catalogo.estatus_con_link;

  function cambiar(campo: keyof EstudioPayload, valor: string | null) {
    setDatos((previo) => {
      const siguiente = { ...previo, [campo]: valor };

      // Los campos condicionales se limpian al dejar de aplicar, para no
      // mandar una fecha que el servidor va a descartar de todos modos.
      if (campo === 'vencimiento' && valor !== catalogo.vencimiento_con_fecha) {
        siguiente.fecha_vencimiento = null;
      }
      if (campo === 'estatus' && valor !== catalogo.estatus_con_link) {
        siguiente.link = null;
      }

      return siguiente;
    });
  }

  const completo =
    datos.despacho.trim() !== '' &&
    datos.estudio.trim() !== '' &&
    datos.vigencia !== '' &&
    datos.prioridad !== '' &&
    datos.tipo !== '' &&
    datos.estatus !== '' &&
    datos.vencimiento !== '' &&
    datos.aprobado !== '' &&
    datos.pagado !== '' &&
    (!pideFecha || (datos.fecha_vencimiento ?? '') !== '') &&
    (!pideLink || (datos.link ?? '').trim() !== '');

  async function confirmar() {
    if (!completo) {
      return;
    }

    await onGuardar({
      ...datos,
      despacho: datos.despacho.trim(),
      estudio: datos.estudio.trim(),
      estudio_ko: (datos.estudio_ko ?? '').trim() || null,
      link: pideLink ? (datos.link ?? '').trim() || null : null,
    });
  }

  return (
    <section className="flex flex-col gap-5 rounded-tarjeta border border-borde bg-fondo-elevado p-5">
      <h2 className="text-base font-semibold text-texto">
        {t(editando ? 'estudios.editando' : 'estudios.nuevo')}
      </h2>

      {/* Dos columnas: la izquierda identifica el estudio (Despacho a
          Prioridad), la derecha lleva su ciclo de vida (IN/EX a Pagado). Cada
          una es su propia pila para que los campos condicionales de la
          derecha (Link, Fecha) no desalineen la izquierda. */}
      <div className="grid gap-x-6 gap-y-4 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <Input
            etiqueta={t('estudios.despacho')}
            name="estudio-despacho"
            value={datos.despacho}
            onChange={(evento) => cambiar('despacho', evento.target.value)}
            disabled={guardando}
            maxLength={150}
          />

          <Textarea
            etiqueta={t('estudios.estudio')}
            name="estudio-nombre"
            value={datos.estudio}
            onChange={(evento) => cambiar('estudio', evento.target.value)}
            disabled={guardando}
            maxLength={2000}
          />

          <Textarea
            etiqueta={t('estudios.estudioKo')}
            ayuda={t('estudios.estudioKoAyuda')}
            name="estudio-coreano"
            value={datos.estudio_ko ?? ''}
            onChange={(evento) => cambiar('estudio_ko', evento.target.value)}
            disabled={guardando}
            maxLength={2000}
          />

          <SelectorEstudio
            id="estudio-vigencia"
            titulo={t('estudios.vigencia')}
            grupo="vigencia"
            opciones={catalogo.vigencias}
            valor={datos.vigencia}
            onElegir={(clave) => cambiar('vigencia', clave)}
            deshabilitado={guardando}
          />

          <SelectorEstudio
            id="estudio-prioridad"
            titulo={t('estudios.prioridad')}
            grupo="prioridad"
            opciones={catalogo.prioridades}
            valor={datos.prioridad}
            onElegir={(clave) => cambiar('prioridad', clave)}
            deshabilitado={guardando}
          />
        </div>

        <div className="flex flex-col gap-4">
          <SelectorEstudio
            id="estudio-tipo"
            titulo={t('estudios.tipo')}
            grupo="tipo"
            opciones={catalogo.tipos}
            valor={datos.tipo}
            onElegir={(clave) => cambiar('tipo', clave)}
            deshabilitado={guardando}
          />

          <SelectorEstudio
            id="estudio-estatus"
            titulo={t('estudios.estatus')}
            grupo="estatus"
            opciones={catalogo.estatus}
            valor={datos.estatus}
            onElegir={(clave) => cambiar('estatus', clave)}
            deshabilitado={guardando}
          />

          {/* El link solo tiene sentido cuando el estudio ya está hecho: vive
              justo debajo del estatus que lo habilita. */}
          {pideLink && (
            <Input
              etiqueta={t('estudios.link')}
              ayuda={t('estudios.linkAyuda')}
              name="estudio-link"
              value={datos.link ?? ''}
              onChange={(evento) => cambiar('link', evento.target.value)}
              disabled={guardando}
              maxLength={500}
            />
          )}

          <SelectorEstudio
            id="estudio-vencimiento"
            titulo={t('estudios.vencimiento')}
            grupo="vencimiento"
            opciones={catalogo.vencimientos}
            valor={datos.vencimiento}
            onElegir={(clave) => cambiar('vencimiento', clave)}
            deshabilitado={guardando}
          />

          {/* Igual que el link: la fecha solo aparece con el vencimiento que
              la pide, justo debajo de su selector. */}
          {pideFecha && (
            <Input
              etiqueta={t('estudios.fechaVencimiento')}
              name="estudio-fecha"
              type="date"
              value={datos.fecha_vencimiento ?? ''}
              onChange={(evento) =>
                cambiar('fecha_vencimiento', evento.target.value || null)
              }
              disabled={guardando}
            />
          )}

          <SelectorEstudio
            id="estudio-aprobado"
            titulo={t('estudios.aprobado')}
            grupo="aprobacion"
            opciones={catalogo.aprobaciones}
            valor={datos.aprobado}
            onElegir={(clave) => cambiar('aprobado', clave)}
            deshabilitado={guardando}
          />

          <SelectorEstudio
            id="estudio-pagado"
            titulo={t('estudios.pagado')}
            grupo="aprobacion"
            opciones={catalogo.aprobaciones}
            valor={datos.pagado}
            onElegir={(clave) => cambiar('pagado', clave)}
            deshabilitado={guardando}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void confirmar()} disabled={!completo} cargando={guardando}>
          {t(editando ? 'estudios.guardarCambios' : 'estudios.confirmar')}
        </Button>

        {editando && (
          <Button variante="fantasma" onClick={onCancelar} disabled={guardando}>
            {t('estudios.cancelarEdicion')}
          </Button>
        )}

        {!completo && (
          <p className="text-sm text-texto-tenue">{t('estudios.faltanCampos')}</p>
        )}
      </div>
    </section>
  );
}

interface SelectorProps {
  /** `grupo` se repite entre campos (aprobado y pagado comparten catálogo). */
  id: string;
  titulo: string;
  grupo: GrupoOpciones;
  opciones: OpcionEstudio[];
  valor: string;
  onElegir: (clave: string) => void;
  deshabilitado: boolean;
}

/**
 * Un campo de selección como desplegable, sin semáforo.
 *
 * El color de cada opción solo se muestra ya capturado, en la tabla de
 * registros: aquí todas las opciones se ven igual, para que elegir una no se
 * sienta como acertar o fallar un color.
 */
function SelectorEstudio({
  id,
  titulo,
  grupo,
  opciones,
  valor,
  onElegir,
  deshabilitado,
}: SelectorProps) {
  const t = useTraduccion();

  function rotulo(opcion: OpcionEstudio): string {
    const clave: ClaveTraduccion | undefined = claveEtiqueta(grupo, opcion.clave);
    return clave ? t(clave) : opcion.etiqueta;
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-texto">
        {titulo}
      </label>

      <select
        id={id}
        className={CLASES_CAMPO}
        value={valor}
        disabled={deshabilitado}
        onChange={(evento) => onElegir(evento.target.value)}
      >
        <option value="">—</option>
        {opciones.map((opcion) => (
          <option key={opcion.clave} value={opcion.clave}>
            {rotulo(opcion)}
          </option>
        ))}
      </select>
    </div>
  );
}
