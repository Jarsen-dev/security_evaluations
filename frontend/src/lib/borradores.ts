/**
 * Borradores de los formularios de Controles, guardados en IndexedDB.
 *
 * Cambiar de pestaña, salir a otra sección o recargar la página desmonta el
 * formulario y se lleva sus `useState`. Estas hojas son largas —hasta 30
 * puntos, con observaciones y fotos— y volver a llenarlas significa volver a
 * caminar la planta, así que lo capturado se persiste y se restaura al volver.
 *
 * **Por qué IndexedDB y no `localStorage`.** Las fotos son `File`, y hay que
 * guardarlas tal cual. `localStorage` solo admite texto: habría que pasarlas a
 * base64 —que infla un tercio— contra una cuota de unos 5 MB. Una hoja de
 * silos son 30 puntos, cada punto en NO admite hasta `MAX_FOTOS` fotos y
 * `REDUCCION_EVIDENCIA` las deja en hasta 2 MB. No cabe. IndexedDB guarda un
 * `File` directo por clonado estructurado y su cuota no es esa.
 *
 * **Sí funciona fuera de contexto seguro**, a diferencia de
 * `crypto.randomUUID` (regla 5 del CLAUDE.md): por la IP de la LAN se
 * comporta igual que por HTTPS. Aun así, nada de aquí es indispensable:
 * ninguna función lanza, y si el navegador no deja persistir, el formulario
 * funciona como siempre, solo que sin red de seguridad.
 */

const BASE = 'esh_borradores';
const ALMACEN = 'borradores';
const VERSION = 1;

export interface Borrador<T> {
  id: string;
  /** Día en que se escribió, `YYYY-MM-DD`. Decide el aviso de "otro día". */
  fecha: string;
  datos: T;
}

/**
 * Abre la base, o devuelve `null` si el navegador no la ofrece.
 *
 * En modo privado, con el almacenamiento bloqueado o si la base está tomada
 * por otra pestaña que no soltó una versión vieja (`onblocked`), se devuelve
 * `null` y quien llama sigue sin persistencia.
 */
function abrir(): Promise<IDBDatabase | null> {
  return new Promise((resolver) => {
    if (typeof indexedDB === 'undefined') {
      resolver(null);
      return;
    }

    let peticion: IDBOpenDBRequest;

    try {
      peticion = indexedDB.open(BASE, VERSION);
    } catch {
      resolver(null);
      return;
    }

    peticion.onupgradeneeded = () => {
      const db = peticion.result;
      if (!db.objectStoreNames.contains(ALMACEN)) {
        db.createObjectStore(ALMACEN, { keyPath: 'id' });
      }
    };

    peticion.onsuccess = () => resolver(peticion.result);
    peticion.onerror = () => resolver(null);
    peticion.onblocked = () => resolver(null);
  });
}

/** Corre una operación sobre el almacén. Nunca lanza: devuelve `null`. */
function conAlmacen<R>(
  modo: IDBTransactionMode,
  operacion: (almacen: IDBObjectStore) => IDBRequest<R>,
): Promise<R | null> {
  return abrir().then(
    (db) =>
      new Promise<R | null>((resolver) => {
        if (db === null) {
          resolver(null);
          return;
        }

        try {
          const transaccion = db.transaction(ALMACEN, modo);
          const peticion = operacion(transaccion.objectStore(ALMACEN));

          peticion.onsuccess = () => resolver(peticion.result);
          // El caso típico aquí es la cuota llena al escribir una foto.
          peticion.onerror = () => resolver(null);
          transaccion.onabort = () => resolver(null);
          transaccion.oncomplete = () => db.close();
        } catch {
          resolver(null);
        }
      }),
  );
}

export async function leerBorrador<T>(id: string): Promise<Borrador<T> | null> {
  const guardado = await conAlmacen<Borrador<T> | undefined>('readonly', (almacen) =>
    almacen.get(id),
  );

  return guardado ?? null;
}

export async function guardarBorrador<T>(
  id: string,
  fecha: string,
  datos: T,
): Promise<void> {
  await conAlmacen('readwrite', (almacen) => almacen.put({ id, fecha, datos }));
}

export async function borrarBorrador(id: string): Promise<void> {
  await conAlmacen('readwrite', (almacen) => almacen.delete(id));
}
