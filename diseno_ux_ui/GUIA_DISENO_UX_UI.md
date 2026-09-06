# Korva Nicaragua 2.0 — Guía de Diseño UX/UI

> **Proyecto:** Korva Nicaragua 2.0
> **Entrega:** Diseño de Experiencia de Usuario (UX) e Interfaz (UI)
> **Estado:** Diseño implementado y documentado
> **Base:** Especificación original (`specification`) + implementación real (`static/css/korva.css`, templates)

---

## 1. Resumen

Korva Nicaragua es una red social y marketplace para microempresas y PyMEs de Nicaragua (inspirado en Binance: reputación por niveles). Esta guía documenta el sistema de diseño, los componentes UI, los flujos de usuario y las decisiones de UX implementadas, siguiendo exactamente la especificación y el código real de la aplicación.

---

## 2. Fundamentos del diseño (tokens)

### 2.1 Paleta de color — Tema oscuro (default)

| Token | Hex | Uso |
|---|---|---|
| `--bg-primary` | `#09090b` | Fondo principal (slate muy oscuro) — alto contraste |
| `--bg-secondary` | `#0c0c0e` | Tarjetas, paneles, navbar |
| `--bg-tertiary` | `#1a1a1d` | Inputs, bordes, zonas de código |
| `--text-primary` | `#e5e7eb` | Texto principal |
| `--text-secondary` | `#9ca3af` | Texto secundario / placeholders |
| `--border-color` | `#1a1a1d` | Bordes por defecto |
| `--border-hover` | `#2d2d33` | Bordes al hover de cards |
| `--btn-primary` | `#10b981` | Verde esmeralda: botones y éxito |
| `--btn-primary-hover` | `#059669` | Hover del verde principal |
| `--btn-secondary` | `#f59e0b` | Ámbar: incentivos y advertencias |

**Origen:** literal de la especificación (fondo `#09090b`, tarjetas `#0c0c0e`, verde esmeralda `#10b981`, ámbar `#f59e0b`) definidos como variables CSS en `static/css/korva.css` y reutilizados por toda la UI.

### 2.2 Tema claro (alternativo)

| Token | Hex |
|---|---|
| `--bg-primary` | `#ffffff` |
| `--bg-secondary` | `#f8fafc` |
| `--bg-tertiary` | `#f1f5f9` |
| `--text-primary` | `#1e293b` |
| `--text-secondary` | `#64748b` |
| `--border-color` | `#e2e8f0` |
| `--border-hover` | `#cbd5e1` |
| `--btn-primary` / hover | `#10b981` / `#059669` (idénticos) |
| `--btn-secondary` | `#f59e0b` |

El usuario puede alternar con un botón sol/luna; la preferencia se persiste (JS `korva.js`, `applyIcon` + `prefers-color-scheme`).

### 2.3 Tipografía

- **Inter** (`sans-serif`): texto general — limpia y sin serifa, ideal para UI. `letter-spacing: -0.011em`, antialiasing.
- **Fira Code** (`monospace`): "números y valores" técnicos/fintech (precios, scores, puntuaciones de popularidad). Clase `.code-font`.

**Origen:** literal de la especificación (Inter + Fira Code, vibe fintech).

---

## 3. Componentes UI

| Componente | Clase | Diseño |
|---|---|---|
| Card / panel | `.korva-card` | Fondo `--bg-secondary`, borde `--border-color`, hover `--border-hover` |
| Botón primario | `.korva-btn-primary` | Verde `#10b981`, hover `#059669` + elevación `translateY(-1px)` + sombra verde |
| Botón secundario | `.korva-btn-secondary` | Ámbar `#f59e0b`, hover `#d97706` |
| Input | `.korva-input` | Fondo `--bg-tertiary`, radius `0.5rem`, focus anillo verde `rgba(16,185,129,.15)` |
| Navbar | `nav.bg-korva-card` | Translúcido: `color-mix 82%` + `backdrop-filter: blur(12px)` |
| Toasts | `.message-toast` | Animación `slideIn 0.3s` + `fadeOut 0.3s`; mensajes de éxito/error |
| Badges / stats | — | Chips Pilares: Plata `#c0c0c0`, Oro `#ffd700`, Bronce `#cd7f32`, VIP `#a855f7` |
| Niveles (Tiers) | — | Bronce 0–999, Plata 1000–2499, Oro 2500–4999, VIP ≥5000 |
| Sello oficial | — | `@verified` = RUC válido (bono +1000 pts) |

---

## 4. Patrones de experiencia (UX)

### 4.1 Navegación
- Navbar fija con logo + enlaces (Muro, Marketplace, Rankings, Mesa de Eventos, Mensajes, Korva IA) + botón de tema + menú de usuario desplegable.
- **Menú de usuario**: clic en avatar abre dropdown (editar perfil, mis reportes, cerrar sesión); se cierra al hacer clic fuera (compatible móvil/táctil).
- Menú móvil tipo hamburguesa con animación (`fa-bars`/`fa-times`).

### 4.2 Perfil (estilo Discord/Binance)
- Banner, avatar circular, badge de tier, stats cards (seguidores, asociados, score).
- **Edición de perfil con mapa**: página `/edit-profile/` incluye un mapa Leaflet arrastrable para fijar latitud/longitud de la empresa + botón "Usar mi ubicación actual" (geolocalización). Los campos `latitude`/`longitude` están como inputs ocultos en el formulario.

### 4.3 Mapa de negocios (`/mapa/`)
- Leaflet + OpenStreetMap (local, sin CDN), marcadores por negocio, popups con enlace al perfil.
- **Filtros**: por ciudad y sector + **buscador** tolerante a tildes (café = cafe, ESTELI = estelí).
- Carga de datos por AJAX (`/mapa/data/`), botones "Filtrar" y "Limpiar".

### 4.4 Feedback al usuario
- Hover/focus en todos los elementos interactivos (elevación, anillos, sombras).
- Toasts para errores/sucesos; mensajes de estado de IA ("escribiendo…").
- Los errores de la IA (quota/503) se reintentan automáticamente (máx. 3) para una experiencia fluida.

### 4.5 Estados de contención y seguridad
- Protección CSRF en formularios; `@login_required` en rutas privadas; validación de RUC y WhatsApp en forms.
- Moderación de posts (estado approved/flagged/removed) + auditoría IA simulada.

---

## 5. Diseño responsive

- **Móvil**: menú hamburguesa, columnas apiladas, tarjetas a ancho completo, mapa ancho completo.
- **Desktop**: navbar completa, grid multi-columna, dropdowns.
- Usa Tailwind (`grid`, `md:`, `lg:`, flex) + `backdrop-filter` en navbar para glassmorphism ligero.

---

## 6. Accesibilidad

- Contraste alto (verde esmeralda sobre fondos oscuros; texto `#e5e7eb` sobre `#09090b`).
- Enlaces/botones con estados `hover`/`focus` visibles.
- `aria-label` en botones de icono y menú móvil.
- Botón de tema accesible (sol/luna con texto alternativo).

---

## 7. Flujo del usuario (journey)

1. **Entrada**: Landing → Registro/Login → Perfil con datos (RUC, ciudad, sector, ubicación en mapa).
2. **Actividad**: Publicar posts/votos en Muro → listar productos en Marketplace con contacto WhatsApp → posicionarse en Rankings (Tiers).
3. **Conexión**: Mensajería privada entre empresas.
4. **Inteligencia**: Korva IA (RUC, DGI, impuestos, envíos) con semillas de consultas.
5. **Control**: Reportes CSV/PDF (KPIs y certificado imprimible).

---

## 8. Bitácora de cambios de diseño

| Fecha | Cambio | Archivo |
|---|---|---|
| — | Tema oscuro + tokens CSS (`:root`, `html.light`) | `static/css/korva.css` |
| — | Menú de usuario desplegable táctil (fix móvil) | `templates/navbar.html`, `static/js/korva.js` |
| Sep 2026 | Editor de ubicación con mapa en editar perfil | `templates/users/edit_profile.html`, `users/forms.py` |
| Sep 2026 | Mapa de negocios con filtros + buscador sin tildes | `templates/map/map.html`, `core/map_views.py` |
| Sep 2026 | Leaflet local (sin CDN) para producción estable | `static/vendor/leaflet/` |

---

*Fin de la Guía de Diseño UX/UI — Korva Nicaragua 2.0.*