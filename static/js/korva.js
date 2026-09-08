        document.querySelectorAll('.message-toast').forEach(el => {
            setTimeout(() => { if (el.parentElement) el.remove(); }, 5000);
        });

    class KorvaSocket {
        constructor(options = {}) {
            this.url = options.url || null;
            this.name = options.name || 'default';
            this.reconnectDelay = 1000;
            this.maxReconnectDelay = 30000;
            this.maxRetries = 20;
            this.retryCount = 0;
            this.ws = null;
            this.listeners = {};
            this.usePolling = false;
            this.pollInterval = options.pollInterval || 5000;
            this.pollUrl = options.pollUrl || null;
            this.pollTimer = null;
            this.onStatusChange = options.onStatusChange || null;
            this.onReconnect = options.onReconnect || null;
            this.onError = options.onError || null;
            if (this.url) this.connect();
        }

        connect() {
            if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return;
            if (this.retryCount >= this.maxRetries) {
                this.fallbackToPolling();
                return;
            }
            try {
                this.ws = new WebSocket(this.url);
                this._updateStatus('connecting');
            } catch (e) {
                console.warn(`[KorvaSocket:${this.name}] WS failed, polling fallback:`, e);
                this.fallbackToPolling();
                return;
            }
            this.ws.onopen = () => {
                this.retryCount = 0;
                this.reconnectDelay = 1000;
                this._updateStatus('connected');
                if (this.onReconnect) this.onReconnect();
            };
            this.ws.onclose = (e) => {
                if (e.code === 1000) return;
                this.ws = null;
                this._updateStatus('disconnected');
                if (!this.usePolling) setTimeout(() => this.connect(), this._jitter());
            };
            this.ws.onerror = () => {
                this._updateStatus('error');
                if (this.onError) this.onError();
            };
            this.ws.onmessage = (e) => {
                try {
                    const data = JSON.parse(e.data);
                    this._emit(data.type || 'message', data);
                } catch {
                    this._emit('message', { raw: e.data });
                }
            };
        }

        _jitter() {
            const delay = Math.min(this.reconnectDelay, this.maxReconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
            this.retryCount++;
            return delay + Math.random() * 1000;
        }

        fallbackToPolling() {
            if (this.usePolling || !this.pollUrl) return;
            this.usePolling = true;
            this._updateStatus('polling');
            this.poll();
            this.pollTimer = setInterval(() => this.poll(), this.pollInterval);
        }

        poll() {
            if (!this.pollUrl) return;
            fetch(this.pollUrl)
                .then(r => r.json())
                .then(data => this._emit('poll', data))
                .catch(() => {});
        }

        send(data) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify(data));
            } else if (this.pollUrl) {
                fetch(this.pollUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this._getCSRF() },
                    body: JSON.stringify(data),
                }).catch(() => {});
            }
        }

        on(event, callback) {
            if (!this.listeners[event]) this.listeners[event] = [];
            this.listeners[event].push(callback);
            return () => { this.listeners[event] = this.listeners[event].filter(fn => fn !== callback); };
        }

        _emit(event, data) {
            (this.listeners[event] || []).forEach(fn => fn(data));
            (this.listeners['*'] || []).forEach(fn => fn(event, data));
        }

        _updateStatus(status) {
            this.status = status;
            if (this.onStatusChange) this.onStatusChange(status);
        }

        _getCSRF() {
            const m = document.cookie.match(/csrftoken=([^;]+)/);
            return m ? m[1] : '';
        }

        disconnect() {
            if (this.pollTimer) clearInterval(this.pollTimer);
            if (this.ws) { this.ws.close(1000); this.ws = null; }
            this._updateStatus('disconnected');
        }

        static manager = { sockets: {} };
        static create(name, options) {
            const sock = new KorvaSocket(options);
            KorvaSocket.manager.sockets[name] = sock;
            return sock;
        }
        static get(name) { return KorvaSocket.manager.sockets[name]; }
    }

    (function() {
        // Indicador de conexión eliminado por solicitud del usuario.
        // Se mantiene la referencia como no-op para no romper llamadas existentes.
        function showStatusIndicator(status) {
            // intencionalmente vacío: no se muestra "Conectando/Conectado/Desconectado"
        }

        window.KorvaSocket = KorvaSocket;
        window.KorvaConnectionStatus = showStatusIndicator;
    })();

    document.addEventListener('DOMContentLoaded', function() {
        const chatSocket = KorvaSocket.create('chat', {
            url: null,
            pollUrl: null,
            pollInterval: 5000,
            onStatusChange: function(status) {
                if (window.KorvaConnectionStatus) KorvaConnectionStatus(status);
            }
        });
        setTimeout(async function() {
            try {
                const r = await fetch('/api/ws-config/');
                if (!r.ok) return;
                const cfg = await r.json();
                if (cfg.ws_url) {
                    chatSocket.url = cfg.ws_url;
                    chatSocket.connect();
                }
                if (cfg.poll_url) {
                    chatSocket.pollUrl = cfg.poll_url;
                    chatSocket.pollUrl2 = cfg.poll_url;
                }
                if (cfg.notification_poll_url) {
                    KorvaSocket.create('notifications', {
                        url: cfg.notification_ws_url || null,
                        pollUrl: cfg.notification_poll_url,
                        pollInterval: 10000,
                    });
                }
            } catch(e) {}
        }, 500);
    });

    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function() {
            navigator.serviceWorker.register('/sw.js').then(function(reg) {
                console.log('SW registrado:', reg.scope);
            }).catch(function(err) {
                console.warn('SW no registrado:', err);
            });
        });
    }

    // Theme Toggle (el estado inicial se aplica en el <head> para evitar flash)
    (function() {
        const html = document.getElementById('html-root');
        const toggleBtn = document.getElementById('theme-toggle');
        const themeIcon = document.getElementById('theme-icon');
        if (!html || !toggleBtn) return;

        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        function applyIcon(isLight) {
            if (!themeIcon) return;
            if (isLight) {
                themeIcon.classList.remove('fa-sun');
                themeIcon.classList.add('fa-moon');
            } else {
                themeIcon.classList.remove('fa-moon');
                themeIcon.classList.add('fa-sun');
            }
        }

        if (savedTheme === 'light' || (!savedTheme && !prefersDark)) {
            html.classList.add('light');
            applyIcon(true);
        }

        toggleBtn.addEventListener('click', function() {
            html.classList.toggle('light');
            const isLight = html.classList.contains('light');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            applyIcon(isLight);
        });

        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
            if (!localStorage.getItem('theme')) {
                if (e.matches) {
                    html.classList.remove('light');
                    applyIcon(false);
                } else {
                    html.classList.add('light');
                    applyIcon(true);
                }
            }
        });
    })();

    // Mobile Menu Toggle
    document.addEventListener('DOMContentLoaded', function() {
        const menuBtn = document.getElementById('mobile-menu-btn');
        const mobileMenu = document.getElementById('mobile-menu');
        const menuIcon = document.getElementById('mobile-menu-icon');

        if (menuBtn && mobileMenu) {
            menuBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                mobileMenu.classList.toggle('hidden');
                menuIcon.classList.toggle('fa-bars');
                menuIcon.classList.toggle('fa-times');
            });

            mobileMenu.querySelectorAll('a').forEach(function(link) {
                link.addEventListener('click', function() {
                    mobileMenu.classList.add('hidden');
                    menuIcon.classList.add('fa-bars');
                    menuIcon.classList.remove('fa-times');
                });
            });

            document.addEventListener('click', function(e) {
                if (!menuBtn.contains(e.target) && !mobileMenu.contains(e.target)) {
                    mobileMenu.classList.add('hidden');
                    menuIcon.classList.add('fa-bars');
                    menuIcon.classList.remove('fa-times');
                }
            });
        }
    });

    // User Dropdown (avatar) - abre al tocar (móvil y desktop)
    document.addEventListener('DOMContentLoaded', function() {
        const btn = document.getElementById('user-menu-btn');
        const dd = document.getElementById('user-menu-dd');

        if (btn && dd) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                dd.classList.toggle('hidden');
            });

            document.addEventListener('click', function(e) {
                if (!btn.contains(e.target) && !dd.contains(e.target)) {
                    dd.classList.add('hidden');
                }
            });
        }
    });

    /* ============ Notificaciones (estilo Facebook) ============ */
    (function() {
        const NOTIF_POLL_URL = '/api/notifications/unread/';
        const NOTIF_LIST_URL = '/notifications/json/';
        let notifCount = 0;

        function esc(s) {
            return String(s || '')
                .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }

        function timeAgo(iso) {
            const d = new Date(iso);
            const diff = (Date.now() - d.getTime()) / 1000;
            if (diff < 60) return 'ahora';
            if (diff < 3600) return Math.floor(diff / 60) + ' min';
            if (diff < 86400) return Math.floor(diff / 3600) + ' h';
            if (diff < 604800) return Math.floor(diff / 86400) + ' d';
            return d.toLocaleDateString('es-NI', { day: 'numeric', month: 'short' });
        }

        const btn = document.getElementById('notif-btn');
        const dd = document.getElementById('notif-dd');
        const badge = document.getElementById('notif-badge');
        const list = document.getElementById('notif-list');
        const empty = document.getElementById('notif-empty');

        if (!btn || !dd) return;

        function showBadge(count) {
            notifCount = count;
            if (!badge) return;
            if (count > 0) {
                badge.classList.remove('hidden');
                badge.textContent = count > 99 ? '99+' : count;
            } else {
                badge.classList.add('hidden');
            }
        }

        function renderList(data) {
            if (!list) return;
            const items = data.notifications || [];
            if (!items.length) {
                list.classList.add('hidden');
                if (empty) empty.classList.remove('hidden');
                return;
            }
            list.classList.remove('hidden');
            if (empty) empty.classList.add('hidden');
            list.innerHTML = items.map(function(n) {
                const cls = n.is_read ? 'opacity-70' : '';
                const avatar = n.sender_avatar
                    ? '<img src="' + esc(n.sender_avatar) + '" class="w-10 h-10 rounded-full object-cover">'
                    : '<div class="w-10 h-10 rounded-full bg-korva-dark-alt flex items-center justify-center text-korva-success"><i class="' + esc(n.icon) + '"></i></div>';
                return '<a href="' + esc(n.url) + '" class="notif-item block px-4 py-3 hover:bg-korva-dark-alt transition flex items-start gap-3 ' + cls + '" data-id="' + n.id + '">' +
                    avatar +
                    '<div class="flex-1 min-w-0">' +
                        '<div class="text-sm text-gray-200 font-medium truncate">' + esc(n.title) + '</div>' +
                        '<div class="text-xs text-gray-500 line-clamp-2">' + esc(n.message) + '</div>' +
                        '<div class="text-[11px] text-gray-600 mt-1">' + timeAgo(n.created_at) + '</div>' +
                    '</div>' +
                    (!n.is_read ? '<span class="w-2 h-2 rounded-full bg-korva-success mt-1 flex-shrink-0"></span>' : '') +
                '</a>';
            }).join('');

            list.querySelectorAll('.notif-item').forEach(function(el) {
                el.addEventListener('click', function() {
                    const id = el.getAttribute('data-id');
                    if (id) markRead(id);
                });
            });
        }

        function fetchCount() {
            fetch(NOTIF_POLL_URL)
                .then(function(r) { return r.json(); })
                .then(function(d) { showBadge(d.count || 0); })
                .catch(function() {});
        }

        function fetchList() {
            if (!list) return;
            list.innerHTML = '<div class="px-4 py-6 text-center text-gray-500 text-sm"><i class="fas fa-spinner fa-spin mr-2"></i>Cargando…</div>';
            fetch(NOTIF_LIST_URL + '?limit=30')
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    renderList(d);
                    showBadge(d.unread || 0);
                })
                .catch(function() {
                    if (list) list.innerHTML = '<div class="px-4 py-6 text-center text-gray-500 text-sm">Error al cargar</div>';
                });
        }

        function markRead(id) {
            fetch('/notifications/' + id + '/read/', { method: 'POST', headers: { 'X-CSRFToken': _getCSRF() } })
                .then(function(r) { return r.json(); })
                .then(function(d) { if (d.unread !== undefined) showBadge(d.unread); })
                .catch(function() {});
        }

        function _getCSRF() {
            const m = document.cookie.match(/csrftoken=([^;]+)/);
            return m ? m[1] : '';
        }

        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const wasHidden = dd.classList.contains('hidden');
            dd.classList.toggle('hidden');
            if (wasHidden) fetchList();
        });

        document.addEventListener('click', function(e) {
            if (!btn.contains(e.target) && !dd.contains(e.target)) {
                dd.classList.add('hidden');
            }
        });

        const readAllBtn = document.getElementById('notif-read-all');
        if (readAllBtn) {
            readAllBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                fetch('/notifications/read-all/', { method: 'POST', headers: { 'X-CSRFToken': _getCSRF() } })
                    .then(function(r) { return r.json(); })
                    .then(function() {
                        showBadge(0);
                        list.querySelectorAll('.notif-item').forEach(function(el) {
                            el.classList.remove('opacity-70');
                            const dot = el.querySelector('.bg-korva-success');
                            if (dot) dot.remove();
                        });
                    })
                    .catch(function() {});
            });
        }

        fetchCount();
        setInterval(fetchCount, 30000);

        function wireSocket() {
            if (!window.KorvaSocket) return;
            const sock = KorvaSocket.get('notifications');
            if (!sock || sock._bellWired) return;
            sock._bellWired = true;
            sock.on('unread_count', function(d) { showBadge(d.count || 0); });
            sock.on('notification_message', function(d) {
                showBadge(notifCount + 1);
                if (d && d.notification && d.notification.id) {
                    fetchList();
                    if ('Notification' in window && Notification.permission === 'granted') {
                        showToast(d.notification.title || 'Nueva notificación', d.notification.message || '');
                    }
                }
            });
        }

        wireSocket();
        setTimeout(wireSocket, 1200);
    })();

    function showToast(title, body) {
        // Toast colgante arriba a la derecha estilo Facebook
        const container = document.getElementById('korva-toast-container');
        const c = container || document.body;
        const toast = document.createElement('div');
        toast.className = 'korva-toast';
        toast.innerHTML = '<div class="font-medium text-sm">' + esc(title) + '</div>' +
            '<div class="text-xs text-gray-500 mt-0.5">' + esc(body) + '</div>';
        toast.style.cssText = 'position:fixed;top:70px;right:16px;max-width:320px;z-index:9999;' +
            'background:var(--bg-secondary);border:1px solid var(--border-color);border-left:3px solid var(--btn-primary);' +
            'padding:10px 14px;border-radius:8px;box-shadow:0 8px 30px rgba(0,0,0,.35);animation:slideIn .3s ease;';
        if (!container) document.body.appendChild(toast); else container.appendChild(toast);
        setTimeout(function() { toast.remove(); }, 4500);
    }

    /* ============ Web Push (suscribirse) ============ */
    (function() {
        function urlBase64ToUint8Array(base64String) {
            const padding = '='.repeat((4 - base64String.length % 4) % 4);
            const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
            const raw = atob(base64);
            const arr = new Uint8Array(raw.length);
            for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
            return arr;
        }

        window.KorvaPush = {
            enabled: false,
            setup: function() {
                if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
                    this.enabled = false;
                    return;
                }
                const publicKey = window.KORVA_VAPID_PUBLIC_KEY;
                if (!publicKey) { this.enabled = false; return; }
                this.enabled = true;

                if (Notification.permission === 'granted' && navigator.serviceWorker.controller) {
                    this.syncSubscription();
                }
            },
            requestPermission: function() {
                var self = this;
                if (!this.enabled) return Promise.reject('Push no disponible');
                if (Notification.permission === 'granted') {
                    return this.syncSubscription();
                }
                return Notification.requestPermission().then(function(perm) {
                    if (perm === 'granted') {
                        return self.syncSubscription();
                    }
                    throw new Error('Permiso denegado');
                });
            },
            syncSubscription: function() {
                var self = this;
                return navigator.serviceWorker.ready.then(function(registration) {
                    return registration.pushManager.getSubscription().then(function(existing) {
                        const subscribe = existing || registration.pushManager.subscribe({
                            userVisibleOnly: true,
                            applicationServerKey: urlBase64ToUint8Array(window.KORVA_VAPID_PUBLIC_KEY)
                        });
                        return subscribe.then(function(subscription) {
                            const sub = subscription.toJSON();
                            return fetch('/notifications/push/subscribe/', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                                body: JSON.stringify({
                                    endpoint: sub.endpoint,
                                    keys: sub.keys
                                })
                            });
                        });
                    });
                });
            }
        };

        function getCsrf() {
            const m = document.cookie.match(/csrftoken=([^;]+)/);
            return m ? m[1] : '';
        }

        function esc(s) {
            return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

        document.addEventListener('DOMContentLoaded', function() {
            window.KorvaPush.setup();
            // Aviso suave para activar push (una sola vez)
            if (window.KorvaPush.enabled && 'Notification' in window && Notification.permission === 'default') {
                const dismissed = localStorage.getItem('korva_push_dismissed');
                if (!dismissed) {
                    // Usa el toast de notificación para proponer activar
                    const container = document.getElementById('korva-toast-container');
                    const c = container || document.body;
                    const el = document.createElement('div');
                    el.className = 'korva-push-prompt';
                    el.innerHTML = '<div class="flex items-start gap-3">' +
                        '<i class="fas fa-bell text-korva-success text-xl mt-0.5"></i>' +
                        '<div class="flex-1"><div class="text-sm font-medium text-gray-200">Activa las notificaciones</div>' +
                        '<div class="text-xs text-gray-500">Recibe avisos de mensajes y actividad, incluso con la app cerrada.</div></div>' +
                        '<div class="text-right flex flex-col gap-2"><button id="korva-push-yes" class="text-xs font-semibold text-korva-success hover:underline">Activar</button>' +
                        '<button id="korva-push-no" class="text-xs text-gray-500 hover:underline">Ahora no</button></div></div>';
                    el.style.cssText = 'position:fixed;bottom:16px;right:16px;max-width:340px;z-index:9999;background:var(--bg-secondary);' +
                        'border:1px solid var(--border-color);border-left:3px solid var(--btn-primary);padding:12px 14px;border-radius:8px;' +
                        'box-shadow:0 8px 30px rgba(0,0,0,.35);animation:slideIn .3s ease;';
                    if (!container) document.body.appendChild(el); else container.appendChild(el);
                    el.querySelector('#korva-push-yes').addEventListener('click', function() {
                        window.KorvaPush.requestPermission()
                            .then(function() {
                                showToast('Notificaciones activadas', 'A partir de ahora recibirás avisos de tu actividad.');
                            })
                            .catch(function() {
                                showToast('No se pudo activar', 'Verifica que tu navegador permita notificaciones.');
                            })
                            .finally(function() { el.remove(); });
                    });
                    el.querySelector('#korva-push-no').addEventListener('click', function() {
                        localStorage.setItem('korva_push_dismissed', '1');
                        el.remove();
                    });
                }
            }
        });
    })();