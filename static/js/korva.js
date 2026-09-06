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