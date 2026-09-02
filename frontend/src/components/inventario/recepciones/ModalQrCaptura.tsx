'use client';

import QRCode from 'qrcode';
import { useEffect, useRef, useState } from 'react';

import { Modal } from '@/components/ui/Modal';
import { ErrorDeApi, crearSesionQr, estadoSesionQr } from '@/lib/api';
import { bilingue, useTraduccion } from '@/lib/i18n';

const OPCIONES_QR = {
  width: 260,
  margin: 2,
  // Fondo blanco y módulos negros: máximo contraste para cámaras de gama baja
  // bajo la luz de la nave.
  color: { dark: '#000000', light: '#ffffff' },
  errorCorrectionLevel: 'M' as const,
};

/** Cada cuánto se pregunta si el celular ya mandó la foto. */
const MS_SONDEO = 2000;

/**
 * Sondeos seguidos que pueden fallar antes de darse por vencido.
 *
 * Un tropiezo de la WiFi o un reinicio del backend no significan que la sesión
 * murió: significa que hay que volver a preguntar. Con esto se aguantan ~10
 * segundos de red mala sin obligar a repetir todo el trámite.
 */
const MAX_FALLOS_SONDEO = 5;

/**
 * Orígenes desde los que el celular **no** puede alcanzar a esta computadora.
 *
 * `localhost` es la propia máquina de quien mira: en el celular resolvería al
 * celular mismo. Es el caso de quien desarrolla, y hay que decirlo en vez de
 * pintar un código que no va a funcionar.
 */
function alcanzableDesdeElCelular(origen: string): boolean {
  return !/^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:|\/|$)/i.test(origen);
}

/**
 * Handoff de la foto entre el celular y la PC.
 *
 * La PC abre una sesión, pinta el QR que apunta a `/re/{sesion}` y pregunta
 * cada dos segundos si ya llegó la foto. Cuando llega, avisa hacia arriba y
 * quien la usa dispara la extracción.
 *
 * **La liga sale de `window.location.origin`, NUNCA de `NEXT_PUBLIC_BASE_URL`.**
 * La sesión es efímera y vive solo en el despliegue que la creó, así que el
 * celular tiene que caer en ese mismo. Con la variable de entorno —que se
 * congela al construir la imagen y apunta al dominio público— el QR mandaba el
 * celular a producción mientras la sesión se quedaba en la computadora del
 * operador: producción no la conocía y respondía «esta sesión de captura ya no
 * está disponible», siempre, sin importar cuán reciente fuera el código. Pasa
 * igual entrando por la IP de la LAN, que es la vía de respaldo cuando el
 * túnel se cae (regla 5).
 *
 * Es lo contrario de los otros QR del sistema —cuestionarios y puntos de
 * rondín—: aquellos llevan un token duradero que sí existe en producción y se
 * imprimen para pegarlos en la pared, así que ahí el dominio público es la
 * respuesta correcta.
 *
 * El sondeo se detiene al cerrar el modal: sin eso, un modal olvidado abierto
 * le pegaría a la API toda la tarde.
 */
export function ModalQrCaptura({
  abierto,
  onCerrar,
  onFotoLista,
}: {
  abierto: boolean;
  onCerrar: () => void;
  onFotoLista: (sesionId: string) => void;
}) {
  const t = useTraduccion();
  const lienzo = useRef<HTMLCanvasElement>(null);
  const [origen, setOrigen] = useState<string | null>(null);
  const [sesion, setSesion] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [recibida, setRecibida] = useState(false);
  const fallos = useRef(0);

  // El origen se lee en un efecto y no al renderizar: el HTML del servidor no
  // sabe por dónde entró el navegador, y calcularlo en el primer render sería
  // justo el desajuste de hidratación que el proyecto evita en todas partes.
  useEffect(() => {
    setOrigen(window.location.origin);
  }, []);

  const utilizable = origen !== null && alcanzableDesdeElCelular(origen);

  // Abre la sesión al abrir el modal, y la olvida al cerrarlo para que la
  // siguiente vez se genere una nueva (la anterior ya expiró o se usó). No se
  // abre ninguna si la liga no le va a servir al celular: sería una sesión
  // huérfana y un código que no lleva a ningún lado.
  useEffect(() => {
    if (!abierto || !utilizable) {
      setSesion(null);
      setError('');
      setRecibida(false);
      return;
    }

    let cancelado = false;

    crearSesionQr()
      .then((nueva) => {
        if (!cancelado) setSesion(nueva.id);
      })
      .catch(() => {
        if (!cancelado) setError(t('recepciones.qrFallo'));
      });

    return () => {
      cancelado = true;
    };
  }, [abierto, utilizable, t]);

  const liga = sesion === null || origen === null ? '' : `${origen}/re/${sesion}`;

  useEffect(() => {
    if (liga === '' || lienzo.current === null) {
      return;
    }

    QRCode.toCanvas(lienzo.current, liga, OPCIONES_QR).catch(() => {
      setError(t('recepciones.qrFallo'));
    });
  }, [liga, t]);

  // El sondeo. Se limpia siempre en el return del efecto.
  useEffect(() => {
    if (!abierto || sesion === null || recibida) {
      return;
    }

    fallos.current = 0;

    const temporizador = setInterval(() => {
      void estadoSesionQr(sesion)
        .then((estado) => {
          fallos.current = 0;
          if (estado === 'subida') {
            setRecibida(true);
            onFotoLista(sesion);
          }
        })
        .catch((error_: unknown) => {
          // Solo un 409 significa que la sesión venció o ya se usó. Antes
          // cualquier tropiezo contaba como vencimiento, así que un bache de
          // WiFi o un reinicio del backend borraban un código que seguía
          // perfectamente vivo.
          if (error_ instanceof ErrorDeApi && error_.status === 409) {
            setError(t('recepciones.qrExpirada'));
            setSesion(null);
            return;
          }

          fallos.current += 1;
          if (fallos.current >= MAX_FALLOS_SONDEO) {
            setError(t('recepciones.qrSinConexion'));
            setSesion(null);
          }
        });
    }, MS_SONDEO);

    return () => clearInterval(temporizador);
  }, [abierto, sesion, recibida, onFotoLista, t]);

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      titulo={t('recepciones.qrTitulo')}
      descripcion={t('recepciones.qrAyuda')}
      ancho="sm"
    >
      <div className="flex flex-col items-center gap-4">
        {error !== '' ? (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        ) : origen !== null && !utilizable ? (
          // Entrando por localhost no hay código que valga: se dice qué hacer
          // en vez de pintar uno que el celular no puede seguir.
          <p role="alert" className="text-sm text-texto-suave">
            {bilingue(t('recepciones.qrSoloLocal'))}
          </p>
        ) : (
          <>
            {/* Fondo blanco fijo: el panel es oscuro y un QR sobre fondo
                oscuro no lo lee ninguna cámara. */}
            <div className="rounded-tarjeta bg-white p-3">
              <canvas ref={lienzo} />
            </div>
            {/* La liga también en texto: si la cámara no coopera —pantalla
                sucia, poca luz— se teclea, y de paso se ve a dónde apunta. */}
            {liga !== '' && (
              <p className="break-all text-center text-xs text-texto-tenue">{liga}</p>
            )}
            <p className="text-sm text-texto-suave" aria-live="polite">
              {bilingue(recibida ? t('recepciones.qrRecibida') : t('recepciones.qrEsperando'))}
            </p>
          </>
        )}
      </div>
    </Modal>
  );
}
