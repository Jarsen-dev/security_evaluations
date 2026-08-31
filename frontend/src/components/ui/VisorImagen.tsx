'use client';

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type PointerEvent as PointerEventReact,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';

import {
  IconoGirarDerecha,
  IconoGirarIzquierda,
  IconoPantallaCompleta,
  IconoSalirPantallaCompleta,
  IconoZoomMas,
  IconoZoomMenos,
} from '@/components/ui/Iconos';
import { bilingue, useIdioma } from '@/lib/i18n';
import { cn } from '@/lib/utils';

/**
 * Visor de imágenes con giro, zoom y arrastre, al estilo de un mapa.
 *
 * Existe porque la foto de una remisión llega como la tomó el operador: de
 * lado, de cabeza, o con la letra demasiado chica para leerla en la pantalla.
 * Sin poder girarla y acercarla, la única salida era abrir la imagen en otra
 * pestaña y perder de vista el formulario que se está corrigiendo.
 *
 * Todo se hace con transformaciones de CSS sobre la misma etiqueta `<img>`: no
 * se toca el archivo ni se vuelve a pedir al servidor. El giro es solo de
 * presentación, así que no se guarda: lo que queda como evidencia es la foto
 * original.
 *
 * Nada aquí necesita contexto seguro (regla 5): eventos de puntero,
 * `ResizeObserver` y `createPortal` funcionan igual entrando por la IP de la
 * LAN. La API de pantalla completa del navegador **no** se usa a propósito:
 * la vista ampliada es una capa propia, que además deja la barra de botones
 * dentro del panel y se cierra con Escape.
 */

/** Límites del zoom del usuario, relativos al tamaño ajustado a la caja. */
const ESCALA_MIN = 0.25;
const ESCALA_MAX = 8;

/** Cuánto acerca o aleja cada paso: un botón, un tope de rueda, un doble clic. */
const PASO = 1.25;

interface Vista {
  /** Zoom pedido por el usuario. 1 = la imagen ajustada a la caja. */
  escala: number;
  /** Desplazamiento en píxeles de pantalla, desde el centro de la caja. */
  x: number;
  y: number;
}

const VISTA_INICIAL: Vista = { escala: 1, x: 0, y: 0 };

interface Medidas {
  /** Caja del visor. */
  cw: number;
  ch: number;
  /** Tamaño ya ajustado de la imagen, antes de transformarla. */
  iw: number;
  ih: number;
  /** Tamaño real del archivo, para el porcentaje. */
  nw: number;
}

const MEDIDAS_CERO: Medidas = { cw: 0, ch: 0, iw: 0, ih: 0, nw: 0 };

function acotar(valor: number): number {
  return Math.min(ESCALA_MAX, Math.max(ESCALA_MIN, valor));
}

interface VisorImagenProps {
  src: string;
  alt: string;
  /** Alto del visor mientras NO está en pantalla completa. */
  className?: string;
}

export function VisorImagen({ src, alt, className }: VisorImagenProps) {
  const { t, locale } = useIdioma();

  const [vista, setVista] = useState<Vista>(VISTA_INICIAL);
  const [rotacion, setRotacion] = useState(0);
  const [completa, setCompleta] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [medidas, setMedidas] = useState<Medidas>(MEDIDAS_CERO);

  const contenedor = useRef<HTMLDivElement>(null);
  const imagen = useRef<HTMLImageElement>(null);
  const arrastre = useRef<{ id: number; px: number; py: number; x: number; y: number } | null>(
    null,
  );

  const medir = useCallback(() => {
    const caja = contenedor.current;
    const img = imagen.current;

    if (caja === null || img === null) {
      return;
    }

    const siguiente: Medidas = {
      cw: caja.clientWidth,
      ch: caja.clientHeight,
      iw: img.clientWidth,
      ih: img.clientHeight,
      nw: img.naturalWidth,
    };

    // Se compara antes de guardar: `ResizeObserver` dispara también cuando
    // nada cambió de tamaño y un `setState` por cada aviso re-renderiza el
    // visor a media inspección.
    setMedidas((previas) =>
      previas.cw === siguiente.cw &&
      previas.ch === siguiente.ch &&
      previas.iw === siguiente.iw &&
      previas.ih === siguiente.ih &&
      previas.nw === siguiente.nw
        ? previas
        : siguiente,
    );
  }, []);

  // Se mide después de pintar, no en el render: al entrar y salir de pantalla
  // completa la caja cambia de tamaño y con ella el ajuste del giro.
  useLayoutEffect(() => {
    medir();
  }, [medir, completa]);

  useEffect(() => {
    const caja = contenedor.current;
    const img = imagen.current;

    if (caja === null || img === null || typeof ResizeObserver === 'undefined') {
      return;
    }

    const observador = new ResizeObserver(medir);
    observador.observe(caja);
    observador.observe(img);

    return () => observador.disconnect();
    // `completa` está en las dependencias porque al ampliar, el visor se
    // vuelve a montar dentro del portal: el nodo observado es otro y sin esto
    // se seguiría midiendo el que ya se desmontó.
  }, [medir, completa]);

  /**
   * Cuánto hay que encoger la imagen girada para que siga cabiendo.
   *
   * Al girar 90° el alto pasa a ocupar el ancho de la caja; sin este factor la
   * hoja se sale por los lados y el operador tiene que alejarla a mano cada
   * vez que endereza una foto.
   */
  const factorGiro =
    rotacion % 180 === 0 || medidas.iw === 0 || medidas.ih === 0
      ? 1
      : Math.min(medidas.cw / medidas.ih, medidas.ch / medidas.iw, 1);

  const escalaTotal = vista.escala * factorGiro;

  // El porcentaje es contra el tamaño real del archivo, que es lo que dice si
  // la letra se va a alcanzar a leer; si todavía no se conoce, se cae al zoom
  // relativo al ajuste.
  const razon =
    medidas.nw > 0 && medidas.iw > 0 ? (medidas.iw * escalaTotal) / medidas.nw : escalaTotal;

  const porcentaje = new Intl.NumberFormat(locale, {
    style: 'percent',
    maximumFractionDigits: 0,
  }).format(razon);

  /**
   * Acerca o aleja dejando quieto el punto señalado.
   *
   * Es lo que hace que la rueda del ratón se sienta como un mapa: sin fijar el
   * cursor, cada tope de rueda mueve el papel bajo la vista y hay que volver a
   * buscar el renglón que se estaba leyendo.
   */
  const zoom = useCallback((factor: number, punto?: { x: number; y: number }) => {
    const caja = contenedor.current?.getBoundingClientRect();

    setVista((previa) => {
      const escala = acotar(previa.escala * factor);

      if (escala === previa.escala) {
        return previa;
      }

      const razonReal = escala / previa.escala;
      // Distancia del punto fijo al centro de la caja, que es el origen de la
      // transformación. Sin punto se toma el centro: la vista se abre y se
      // cierra sobre sí misma.
      const dx = caja === undefined || punto === undefined ? 0 : punto.x - (caja.left + caja.width / 2);
      const dy = caja === undefined || punto === undefined ? 0 : punto.y - (caja.top + caja.height / 2);

      return {
        escala,
        x: (1 - razonReal) * dx + razonReal * previa.x,
        y: (1 - razonReal) * dy + razonReal * previa.y,
      };
    });
  }, []);

  function girar(grados: number) {
    setRotacion((previa) => (previa + grados + 360) % 360);
    // Enderezar una foto es empezar a mirarla de nuevo: el encuadre anterior
    // ya no corresponde a nada.
    setVista(VISTA_INICIAL);
  }

  // La rueda del ratón va como oyente nativo y no como `onWheel`: React
  // registra ese evento en modo pasivo, donde `preventDefault()` no hace nada
  // y la página entera se desplaza mientras se intenta acercar la foto.
  useEffect(() => {
    const caja = contenedor.current;

    if (caja === null) {
      return;
    }

    function alGirarLaRueda(evento: WheelEvent) {
      evento.preventDefault();
      zoom(evento.deltaY < 0 ? PASO : 1 / PASO, { x: evento.clientX, y: evento.clientY });
    }

    caja.addEventListener('wheel', alGirarLaRueda, { passive: false });
    return () => caja.removeEventListener('wheel', alGirarLaRueda);
    // Misma razón que en el observador: al ampliar cambia el nodo.
  }, [zoom, completa]);

  // En pantalla completa, Escape cierra y el fondo no se desplaza: la capa
  // tapa el panel y desplazarlo por detrás desorienta al volver.
  useEffect(() => {
    if (!completa) {
      return;
    }

    function alPresionarTecla(evento: KeyboardEvent) {
      if (evento.key === 'Escape') {
        setCompleta(false);
      }
    }

    document.addEventListener('keydown', alPresionarTecla);
    const overflowPrevio = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', alPresionarTecla);
      document.body.style.overflow = overflowPrevio;
    };
  }, [completa]);

  function empezarArrastre(evento: PointerEventReact<HTMLDivElement>) {
    // Solo el botón izquierdo: el derecho abre el menú del navegador y el de
    // en medio desplaza la página.
    if (evento.pointerType === 'mouse' && evento.button !== 0) {
      return;
    }

    evento.currentTarget.setPointerCapture(evento.pointerId);
    arrastre.current = {
      id: evento.pointerId,
      px: evento.clientX,
      py: evento.clientY,
      x: vista.x,
      y: vista.y,
    };
    setArrastrando(true);
  }

  function moverArrastre(evento: PointerEventReact<HTMLDivElement>) {
    const inicio = arrastre.current;

    if (inicio === null || inicio.id !== evento.pointerId) {
      return;
    }

    setVista((previa) => ({
      ...previa,
      x: inicio.x + (evento.clientX - inicio.px),
      y: inicio.y + (evento.clientY - inicio.py),
    }));
  }

  function soltarArrastre(evento: PointerEventReact<HTMLDivElement>) {
    if (arrastre.current?.id !== evento.pointerId) {
      return;
    }

    arrastre.current = null;
    setArrastrando(false);
  }

  // "Nadie la ha tocado todavía": la imagen sigue tal como se abrió.
  const sinTocar = vista.escala === 1 && vista.x === 0 && vista.y === 0 && rotacion === 0;

  const barra = (
    <div
      className={cn(
        'absolute left-1/2 top-3 z-10 flex -translate-x-1/2 items-center gap-1 rounded-md',
        'border border-borde bg-fondo-elevado/90 px-1.5 py-1 shadow-lg backdrop-blur-sm',
      )}
      // La barra flota encima de la foto: sin esto, empezar a arrastrar sobre
      // un botón movería la imagen en vez de pulsarlo.
      onPointerDown={(evento) => evento.stopPropagation()}
    >
      <BotonVisor etiqueta={t('visor.girarIzquierda')} onClick={() => girar(-90)}>
        <IconoGirarIzquierda tamano={18} />
      </BotonVisor>
      <BotonVisor etiqueta={t('visor.girarDerecha')} onClick={() => girar(90)}>
        <IconoGirarDerecha tamano={18} />
      </BotonVisor>

      <span className="mx-0.5 h-5 w-px bg-borde" aria-hidden />

      <BotonVisor
        etiqueta={t('visor.alejar')}
        onClick={() => zoom(1 / PASO)}
        deshabilitado={vista.escala <= ESCALA_MIN}
      >
        <IconoZoomMenos tamano={18} />
      </BotonVisor>
      <button
        type="button"
        title={t('visor.ajustar')}
        aria-label={t('visor.ajustar')}
        onClick={() => {
          setVista(VISTA_INICIAL);
          setRotacion(0);
        }}
        className="min-w-[3.25rem] rounded px-1 py-1 text-xs tabular-nums text-texto-suave transition-colors hover:bg-fondo-sutil hover:text-texto"
      >
        {porcentaje}
      </button>
      <BotonVisor
        etiqueta={t('visor.acercar')}
        onClick={() => zoom(PASO)}
        deshabilitado={vista.escala >= ESCALA_MAX}
      >
        <IconoZoomMas tamano={18} />
      </BotonVisor>

      <span className="mx-0.5 h-5 w-px bg-borde" aria-hidden />

      <BotonVisor
        etiqueta={completa ? t('visor.salirPantallaCompleta') : t('visor.pantallaCompleta')}
        onClick={() => setCompleta((previa) => !previa)}
      >
        {completa ? (
          <IconoSalirPantallaCompleta tamano={18} />
        ) : (
          <IconoPantallaCompleta tamano={18} />
        )}
      </BotonVisor>
    </div>
  );

  const visor = (
    <div
      ref={contenedor}
      className={cn(
        'relative select-none overflow-hidden bg-fondo',
        arrastrando ? 'cursor-grabbing' : 'cursor-grab',
        completa ? 'h-full w-full' : className,
      )}
      style={{
        // Fuera de pantalla completa el dedo tiene que poder seguir
        // desplazando la página: el visor ocupa media pantalla del celular.
        touchAction: completa ? 'none' : 'pan-y',
      }}
      onPointerDown={empezarArrastre}
      onPointerMove={moverArrastre}
      onPointerUp={soltarArrastre}
      onPointerCancel={soltarArrastre}
      onDoubleClick={(evento) => zoom(PASO * PASO, { x: evento.clientX, y: evento.clientY })}
    >
      {barra}

      {/* La ayuda se muestra solo mientras nadie ha tocado la imagen: en
          cuanto se gira, se acerca o se arrastra, ya se descubrió el gesto y
          el letrero solo taparía el pie de la hoja. */}
      {sinTocar && (
        <p className="pointer-events-none absolute bottom-3 left-1/2 z-10 hidden -translate-x-1/2 rounded-md border border-borde bg-fondo-elevado/85 px-2 py-1 text-center text-xs text-texto-suave sm:block">
          {bilingue(t('visor.ayuda'))}
        </p>
      )}

      <div className="flex h-full w-full items-center justify-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imagen}
          src={src}
          alt={alt}
          onLoad={medir}
          draggable={false}
          className={cn(
            'max-h-full max-w-full object-contain',
            // La transición se apaga mientras se arrastra: con ella, la
            // imagen persigue al cursor con retraso y se siente pegajosa.
            arrastrando ? '' : 'transition-transform duration-150',
          )}
          style={{
            transform: `translate(${vista.x}px, ${vista.y}px) scale(${escalaTotal}) rotate(${rotacion}deg)`,
          }}
        />
      </div>
    </div>
  );

  if (!completa) {
    return visor;
  }

  // La capa se cuelga del `body`: dentro del panel quedaría atrapada en la
  // tarjeta que la contiene, que recorta lo que se sale y compite por el
  // apilamiento con el encabezado fijo.
  return (
    <>
      {/* Hueco del mismo alto para que el formulario de al lado no salte
          mientras la foto está ampliada. */}
      <div className={className} />
      {createPortal(
        <div className="fixed inset-0 z-50 bg-black/90 p-2 sm:p-6">{visor}</div>,
        document.body,
      )}
    </>
  );
}

/** Botón cuadrado de la barra: solo icono, con el nombre de la acción encima. */
function BotonVisor({
  etiqueta,
  onClick,
  deshabilitado = false,
  children,
}: {
  etiqueta: string;
  onClick: () => void;
  deshabilitado?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      // El texto traducido va en el `title` y en el `aria-label`, donde el
      // salto de línea del coreano ya se pinta como dos renglones (regla 6).
      title={etiqueta}
      aria-label={etiqueta}
      onClick={onClick}
      disabled={deshabilitado}
      className={cn(
        'flex h-8 w-8 items-center justify-center rounded text-texto-suave transition-colors',
        'hover:bg-fondo-sutil hover:text-texto disabled:cursor-not-allowed disabled:opacity-40',
        'disabled:hover:bg-transparent disabled:hover:text-texto-suave',
      )}
    >
      {children}
    </button>
  );
}
