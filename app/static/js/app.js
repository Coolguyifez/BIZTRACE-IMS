/* =====================================================
   BIZTRACE IMS
   APPLICATION JAVASCRIPT
===================================================== */


/* =====================================================
   COMPANY SETTINGS
   These values are injected by Flask/Jinja.
===================================================== */

window.BizFlowSettings = window.BizFlowSettings || {
    currencyCode: "NGN",
    currencySymbol: "₦",
    decimalPlaces: 2,
    currencyPosition: "before",
    dateFormat: "DD/MM/YYYY",
    timeFormat: "12h",
    timezone: "Africa/Lagos"
};


/* =====================================================
   SIDEBAR
===================================================== */

const sidebar =
    document.getElementById("sidebar");

const sidebarToggle =
    document.getElementById("sidebarToggle");

const sidebarOverlay =
    document.getElementById("sidebarOverlay");


if (sidebarToggle) {

    sidebarToggle.addEventListener(
        "click",
        () => {

            if (window.innerWidth <= 991) {

                if (sidebar) {

                    sidebar.classList.toggle(
                        "mobile-open"
                    );

                }

                if (sidebarOverlay) {

                    sidebarOverlay.classList.toggle(
                        "active"
                    );

                }

            } else {

                if (sidebar) {

                    sidebar.classList.toggle(
                        "collapsed"
                    );

                }

            }

        }
    );

}


if (sidebarOverlay) {

    sidebarOverlay.addEventListener(
        "click",
        () => {

            if (sidebar) {

                sidebar.classList.remove(
                    "mobile-open"
                );

            }

            sidebarOverlay.classList.remove(
                "active"
            );

        }
    );

}


/* =====================================================
   CLOSE MOBILE SIDEBAR AFTER NAVIGATION
===================================================== */

document.querySelectorAll(
    ".nav-item"
).forEach(
    item => {

        item.addEventListener(
            "click",
            () => {

                if (
                    window.innerWidth <= 991
                ) {

                    if (sidebar) {

                        sidebar.classList.remove(
                            "mobile-open"
                        );

                    }

                    if (sidebarOverlay) {

                        sidebarOverlay.classList.remove(
                            "active"
                        );

                    }

                }

            }
        );

    }
);


/* =====================================================
   THEME MANAGEMENT
===================================================== */

const themeToggle =
    document.getElementById(
        "themeToggle"
    );

const THEME_KEY =
    "bizflow-theme";

const mediaQuery =
    window.matchMedia(
        "(prefers-color-scheme: dark)"
    );


/* -----------------------------------------------------
   Get current theme preference
----------------------------------------------------- */

function getSavedTheme() {

    return (
        localStorage.getItem(
            THEME_KEY
        ) || "system"
    );

}


/* -----------------------------------------------------
   Notify application that theme changed
----------------------------------------------------- */

function notifyThemeChange() {

    window.dispatchEvent(
        new CustomEvent(
            "themechange"
        )
    );

}


/* -----------------------------------------------------
   Apply theme
----------------------------------------------------- */

function applyTheme(theme) {

    const html =
        document.documentElement;


    html.setAttribute(
        "data-theme",
        theme
    );


    localStorage.setItem(
        THEME_KEY,
        theme
    );


    resolveSystemTheme();


    updateThemeIcon(
        theme
    );


    notifyThemeChange();

}


/* -----------------------------------------------------
   Resolve system theme
----------------------------------------------------- */

function resolveSystemTheme() {

    const html =
        document.documentElement;

    const theme =
        html.getAttribute(
            "data-theme"
        );


    if (theme === "light") {

        html.classList.remove(
            "system-dark"
        );

        return;

    }


    if (theme === "dark") {

        html.classList.remove(
            "system-dark"
        );

        return;

    }


    const prefersDark =
        mediaQuery.matches;


    html.classList.toggle(
        "system-dark",
        prefersDark
    );

}


/* -----------------------------------------------------
   Theme icon
----------------------------------------------------- */

function updateThemeIcon(theme) {

    if (!themeToggle) {

        return;

    }


    const icon =
        themeToggle.querySelector(
            "i"
        );


    if (!icon) {

        return;

    }


    icon.className = "";


    if (theme === "light") {

        icon.className =
            "bi bi-sun-fill";

    }

    else if (theme === "dark") {

        icon.className =
            "bi bi-moon-stars-fill";

    }

    else {

        icon.className =
            "bi bi-circle-half";

    }

}


/* -----------------------------------------------------
   Initial theme
----------------------------------------------------- */

const initialTheme =
    getSavedTheme();


document.documentElement.setAttribute(
    "data-theme",
    initialTheme
);


resolveSystemTheme();


updateThemeIcon(
    initialTheme
);


/* -----------------------------------------------------
   Theme button
----------------------------------------------------- */

if (themeToggle) {

    themeToggle.addEventListener(
        "click",
        function () {

            const current =
                document.documentElement
                    .getAttribute(
                        "data-theme"
                    );


            let nextTheme;


            if (
                current === "system"
            ) {

                nextTheme =
                    "light";

            }

            else if (
                current === "light"
            ) {

                nextTheme =
                    "dark";

            }

            else {

                nextTheme =
                    "system";

            }


            applyTheme(
                nextTheme
            );

        }
    );

}


/* -----------------------------------------------------
   Listen for OS theme changes
----------------------------------------------------- */

mediaQuery.addEventListener(
    "change",
    function () {

        const current =
            document.documentElement
                .getAttribute(
                    "data-theme"
                );


        if (
            current === "system"
        ) {

            resolveSystemTheme();

            notifyThemeChange();

        }

    }
);


/* =====================================================
   COMPANY CURRENCY
===================================================== */


/*
 * Safely obtain the configured currency symbol.
 */

function getCurrencySymbol() {

    const symbol =
        window.BizFlowSettings
            ?.currencySymbol;


    if (
        symbol !== undefined &&
        symbol !== null &&
        String(symbol).trim() !== ""
    ) {

        return String(symbol);

    }


    return "₦";

}


/*
 * Safely obtain currency code.
 */

function getCurrencyCode() {

    const code =
        window.BizFlowSettings
            ?.currencyCode;


    if (
        code !== undefined &&
        code !== null &&
        String(code).trim() !== ""
    ) {

        return String(code);

    }


    return "NGN";

}


/*
 * Safely obtain decimal places.
 */

function getCurrencyDecimalPlaces() {

    const value =
        Number(
            window.BizFlowSettings
                ?.decimalPlaces
        );


    if (
        Number.isInteger(value) &&
        value >= 0 &&
        value <= 6
    ) {

        return value;

    }


    return 2;

}


/*
 * Safely obtain currency position.
 */

function getCurrencyPosition() {

    const position =
        window.BizFlowSettings
            ?.currencyPosition;


    if (
        position === "after"
    ) {

        return "after";

    }


    return "before";

}


/* =====================================================
   FULL MONEY FORMAT
===================================================== */

function formatFullMoney(amount) {

    const numericAmount =
        Number(amount);


    if (
        !Number.isFinite(
            numericAmount
        )
    ) {

        return formatFullMoney(0);

    }


    const decimalPlaces =
        getCurrencyDecimalPlaces();

    const symbol =
        getCurrencySymbol();

    const formatted =
        numericAmount.toLocaleString(
            undefined,
            {
                minimumFractionDigits:
                    decimalPlaces,

                maximumFractionDigits:
                    decimalPlaces
            }
        );


    if (
        getCurrencyPosition() ===
        "after"
    ) {

        return (
            formatted +
            " " +
            symbol
        );

    }


    return (
        symbol +
        formatted
    );

}


/* =====================================================
   COMPACT MONEY FORMAT
===================================================== */

function formatCompactMoney(amount) {

    amount =
        Number(amount);


    if (
        !Number.isFinite(
            amount
        )
    ) {

        return formatFullMoney(0);

    }


    const decimalPlaces =
        getCurrencyDecimalPlaces();

    const symbol =
        getCurrencySymbol();

    const position =
        getCurrencyPosition();

    const sign =
        amount < 0
            ? "-"
            : "";

    const value =
        Math.abs(amount);


    let compactValue;
    let suffix = "";


    if (
        value >= 1000000000
    ) {

        compactValue =
            value / 1000000000;

        suffix = "B";

    }

    else if (
        value >= 1000000
    ) {

        compactValue =
            value / 1000000;

        suffix = "M";

    }

    else if (
        value >= 1000
    ) {

        compactValue =
            value / 1000;

        suffix = "K";

    }

    else {

        return formatFullMoney(
            amount
        );

    }


    const compactDecimals =
        Math.min(
            decimalPlaces,
            2
        );


    const formatted =
        compactValue.toLocaleString(
            undefined,
            {
                minimumFractionDigits:
                    compactDecimals,

                maximumFractionDigits:
                    compactDecimals
            }
        );


    const valueWithSuffix =
        sign +
        formatted +
        suffix;


    if (
        position === "after"
    ) {

        return (
            valueWithSuffix +
            " " +
            symbol
        );

    }


    return (
        sign +
        symbol +
        formatted +
        suffix
    );

}


/* =====================================================
   RESPONSIVE MONEY
===================================================== */

function updateResponsiveMoney() {

    document
        .querySelectorAll(
            ".responsive-money"
        )
        .forEach(
            function (element) {

                const amount =
                    Number(
                        element.dataset.value
                    );


                if (
                    !Number.isFinite(
                        amount
                    )
                ) {

                    return;

                }


                element.textContent =
                    formatFullMoney(
                        amount
                    );


                if (
                    element.scrollWidth >
                    element.clientWidth
                ) {

                    element.textContent =
                        formatCompactMoney(
                            amount
                        );

                }

            }
        );

}


/* =====================================================
   INITIAL LOAD
===================================================== */

function initializeResponsiveMoney() {

    document
        .querySelectorAll(
            ".responsive-money"
        )
        .forEach(
            function (element) {

                if (
                    !element.dataset.value
                ) {

                    const rawValue =
                        element.textContent
                            .replace(
                                /[^\d.-]/g,
                                ""
                            )
                            .trim();


                    if (
                        rawValue !== ""
                    ) {

                        element.dataset.value =
                            rawValue;

                    }

                }

            }
        );


    updateResponsiveMoney();

}


document.addEventListener(
    "DOMContentLoaded",
    initializeResponsiveMoney
);


/* =====================================================
   RESIZE OBSERVER
===================================================== */

let moneyResizeObserver = null;


if (
    typeof ResizeObserver !==
    "undefined"
) {

    moneyResizeObserver =
        new ResizeObserver(
            function () {

                updateResponsiveMoney();

            }
        );


    document
        .querySelectorAll(
            ".stats-card"
        )
        .forEach(
            function (card) {

                moneyResizeObserver.observe(
                    card
                );

            }
        );

}


/* =====================================================
   WINDOW RESIZE
===================================================== */

window.addEventListener(
    "resize",
    updateResponsiveMoney
);


/* =====================================================
   THEME CHANGE
===================================================== */

window.addEventListener(
    "themechange",
    function () {

        requestAnimationFrame(
            updateResponsiveMoney
        );

    }
);


/* =====================================================
   CURRENCY SETTINGS CHANGE
===================================================== */

window.addEventListener(
    "currencychange",
    function () {

        updateResponsiveMoney();

    }
);


/* ============================================================
   BIZTRACE IMS
   NOTIFICATION CENTER
============================================================ */

const NotificationManager = {

    /* ========================================================
       STATE
    ======================================================== */

    notifications: [],

    knownNotificationIds:
        new Set(),

    initialLoadComplete:
        false,

    unreadCount:
        0,


    /* ========================================================
       SOUND PREFERENCES
       
       IMPORTANT:
       These preferences control ONLY sounds.

       They do NOT control notification delivery.
       Notification delivery is controlled by
       NotificationAssignment on the server.
    ======================================================== */

    soundPreferences: {

        enabled:
            true,

        success:
            true,

        system:
            true,

        error:
            true,

        low_stock:
            true,

        gross_loss:
            true,

        net_loss:
            true

    },


    audioUnlocked:
        false,

    pendingSound:
        null,

    audioContext:
        null,

    sounds: {},


    /* ========================================================
       PUSH STATE
    ======================================================== */

    serviceWorkerRegistration:
        null,

    pushSubscription:
        null,

    pushEnabled:
        false,

    pushStateChecked:
        false,


    /* ========================================================
       INITIALIZE
    ======================================================== */

    async init() {

        console.log(
            "BizTrace notification manager starting..."
        );


        this.loadSounds();


        this.bindEvents();


        await this.registerServiceWorker();


        this.bindServiceWorkerMessages();


        await this.syncPushSubscriptionState();


        /*
         * Initial notifications must NOT play sounds.
         */

        await this.loadNotifications({
            playSound:
                false
        });


        await this.updatePushButton();


        this.updateRelativeTimes();


        /*
         * Poll every 15 seconds.
         */

        setInterval(
            () => {

                this.loadNotifications();

            },
            15000
        );


        /*
         * Update relative timestamps.
         */

        setInterval(
            () => {

                this.updateRelativeTimes();

            },
            30000
        );


        console.log(
            "BizTrace notification manager ready."
        );

    },


    /* ========================================================
       AUDIO
    ======================================================== */

    loadSounds() {

        const soundFiles = {

            success:
                "/static/sounds/success.mp3",

            system:
                "/static/sounds/system.mp3",

            error:
                "/static/sounds/error.mp3",

            "low-stock":
                "/static/sounds/low-stock.mp3",

            "gross-loss":
                "/static/sounds/gross-loss.mp3",

            "net-loss":
                "/static/sounds/net-loss.mp3"

        };


        Object.entries(
            soundFiles
        ).forEach(
            ([name, path]) => {

                const audio =
                    new Audio();


                audio.preload =
                    "auto";


                audio.src =
                    path;


                audio.volume =
                    1.0;


                audio.addEventListener(
                    "canplaythrough",
                    () => {

                        console.log(
                            `BizTrace sound ready: ${name}`
                        );

                    },
                    {
                        once:
                            true
                    }
                );


                audio.addEventListener(
                    "error",
                    () => {

                        console.error(
                            `BizTrace notification sound failed to load: ${path}`
                        );

                    }
                );


                this.sounds[name] =
                    audio;

            }
        );


        console.log(
            "BizTrace notification sounds loaded."
        );

    },


    /* ========================================================
       AUDIO UNLOCK
    ======================================================== */

    async unlockAudio() {

        if (
            this.audioUnlocked
        ) {

            return true;

        }


        try {

            const AudioContext =
                window.AudioContext ||
                window.webkitAudioContext;


            if (AudioContext) {

                if (
                    !this.audioContext
                ) {

                    this.audioContext =
                        new AudioContext();

                }


                if (
                    this.audioContext.state ===
                    "suspended"
                ) {

                    await this.audioContext.resume();

                }

            }


            const testAudio =
                this.sounds.success;


            if (testAudio) {

                testAudio.muted =
                    true;


                testAudio.currentTime =
                    0;


                try {

                    const promise =
                        testAudio.play();


                    if (promise) {

                        await promise;

                    }

                } catch (error) {

                    console.warn(
                        "BizTrace silent audio unlock failed:",
                        error
                    );

                }


                testAudio.pause();


                testAudio.currentTime =
                    0;


                testAudio.muted =
                    false;

            }


            this.audioUnlocked =
                true;


            console.log(
                "BizTrace notification audio unlocked."
            );


            await this.flushPendingSound();


            return true;

        } catch (error) {

            console.warn(
                "Unable to unlock notification audio:",
                error
            );


            return false;

        }

    },


    /* ========================================================
       SOUND PREFERENCE
    ======================================================== */

    shouldPlaySound(
        soundType
    ) {

        if (
            !this.soundPreferences.enabled
        ) {

            return false;

        }


        const normalized =
            String(
                soundType || ""
            )
                .trim()
                .toLowerCase()
                .replace(
                    /_/g,
                    "-"
                );


        const preferenceMap = {

            success:
                "success",

            system:
                "system",

            error:
                "error",

            "low-stock":
                "low_stock",

            "gross-loss":
                "gross_loss",

            "net-loss":
                "net_loss"

        };


        const preference =
            preferenceMap[
                normalized
            ];


        /*
         * If a known sound has been disabled,
         * do not play it.
         */

        if (
            preference &&
            this.soundPreferences[
                preference
            ] === false
        ) {

            console.log(
                `BizTrace sound disabled: ${normalized}`
            );


            return false;

        }


        return true;

    },


    /* ========================================================
       RESOLVE SOUND
       
       IMPORTANT:
       notification.category is a DELIVERY category.

       notification.sound is the SOUND category.

       We do NOT convert:
       inventory -> low-stock
       financial -> gross-loss
       etc.

       The backend explicitly supplies the sound.
    ======================================================== */

    resolveNotificationSound(
        notification
    ) {

        if (!notification) {

            return null;

        }


        if (
            notification.sound
        ) {

            const sound =
                String(
                    notification.sound
                )
                    .trim()
                    .toLowerCase()
                    .replace(
                        /_/g,
                        "-"
                    );


            const validSounds = new Set([
                "success",
                "system",
                "error",
                "low-stock",
                "gross-loss",
                "net-loss"
            ]);


            if (
                validSounds.has(
                    sound
                )
            ) {

                return sound;

            }

        }


        /*
         * No explicit sound means:
         * no sound.
         *
         * This is important because notification
         * categories are NOT sound categories.
         */

        return null;

    },


    /* ========================================================
       PLAY SOUND
    ======================================================== */

    async playSound(
        soundType,
        force = false
    ) {

        if (!soundType) {

            return false;

        }


        soundType =
            String(
                soundType
            )
                .trim()
                .toLowerCase()
                .replace(
                    /_/g,
                    "-"
                );


        if (
            !force &&
            !this.shouldPlaySound(
                soundType
            )
        ) {

            return false;

        }


        /*
         * Browser autoplay protection.
         */

        if (
            !this.audioUnlocked
        ) {

            this.pendingSound =
                soundType;


            console.log(
                "Notification sound queued:",
                soundType
            );


            return false;

        }


        /*
         * Try MP3.
         */

        const audio =
            this.sounds[
                soundType
            ];


        if (audio) {

            try {

                audio.pause();


                audio.currentTime =
                    0;


                audio.volume =
                    1.0;


                const playPromise =
                    audio.play();


                if (playPromise) {

                    await playPromise;

                }


                console.log(
                    `BizTrace ${soundType} sound played.`
                );


                return true;

            } catch (error) {

                console.warn(
                    `MP3 failed for ${soundType}; using fallback tone.`,
                    error
                );

            }

        }


        /*
         * Fallback Web Audio.
         */

        return this.playFallbackTone(
            soundType
        );

    },


    /* ========================================================
       FALLBACK TONE
    ======================================================== */

    async playFallbackTone(
        soundType
    ) {

        try {

            const AudioContext =
                window.AudioContext ||
                window.webkitAudioContext;


            if (!AudioContext) {

                return false;

            }


            if (
                !this.audioContext
            ) {

                this.audioContext =
                    new AudioContext();

            }


            if (
                this.audioContext.state ===
                "suspended"
            ) {

                await this.audioContext.resume();

            }


            const frequencies = {

                success:
                    880,

                system:
                    600,

                error:
                    220,

                "low-stock":
                    440,

                "gross-loss":
                    180,

                "net-loss":
                    160

            };


            const frequency =
                frequencies[
                    soundType
                ] || 600;


            const oscillator =
                this.audioContext
                    .createOscillator();


            const gain =
                this.audioContext
                    .createGain();


            oscillator.type =
                "sine";


            oscillator.frequency.value =
                frequency;


            gain.gain.setValueAtTime(
                0.0001,
                this.audioContext.currentTime
            );


            gain.gain.exponentialRampToValueAtTime(
                0.15,
                this.audioContext.currentTime +
                0.02
            );


            gain.gain.exponentialRampToValueAtTime(
                0.0001,
                this.audioContext.currentTime +
                0.35
            );


            oscillator.connect(
                gain
            );


            gain.connect(
                this.audioContext.destination
            );


            oscillator.start();


            oscillator.stop(
                this.audioContext.currentTime +
                0.35
            );


            return true;

        } catch (error) {

            console.error(
                "Fallback notification sound failed:",
                error
            );


            return false;

        }

    },


    /* ========================================================
       PENDING SOUND
    ======================================================== */

    async flushPendingSound() {

        if (
            !this.pendingSound
        ) {

            return;

        }


        const sound =
            this.pendingSound;


        this.pendingSound =
            null;


        await this.playSound(
            sound
        );

    },


    /* ========================================================
       SERVICE WORKER MESSAGES
    ======================================================== */

    bindServiceWorkerMessages() {

        if (
            !("serviceWorker" in navigator)
        ) {

            return;

        }


        navigator.serviceWorker.addEventListener(
            "message",
            async event => {

                const data =
                    event.data;


                if (!data) {

                    return;

                }


                if (
                    data.type !==
                    "BIZTRACE_NOTIFICATION"
                ) {

                    return;

                }


                const notification =
                    data.notification;


                if (!notification) {

                    return;

                }


                console.log(
                    "BizTrace realtime notification:",
                    notification
                );


                const notificationId =
                    String(
                        notification.id
                    );


                /*
                 * Prevent duplicates.
                 */

                const exists =
                    this.notifications.some(
                        item =>
                            String(
                                item.id
                            ) ===
                            notificationId
                    );


                if (!exists) {

                    const normalized = {

                        id:
                            notification.id,

                        title:
                            notification.title ||
                            "BizTrace IMS",

                        message:
                            notification.message ||
                            "You have a new notification.",

                        /*
                         * DELIVERY CATEGORY
                         */

                        category:
                            notification.category ||
                            "system",

                        priority:
                            notification.priority ||
                            "normal",

                        /*
                         * SOUND CATEGORY
                         */

                        sound:
                            notification.sound ||
                            null,

                        is_read:
                            false,

                        details_url:
                            notification.details_url ||
                            `/notifications/${notification.id}`,

                        source_link:
                            notification.link ||
                            null,

                        created_at:
                            notification.created_at ||
                            new Date().toISOString()

                    };


                    this.notifications.unshift(
                        normalized
                    );

                }


                this.knownNotificationIds.add(
                    notificationId
                );


                const sound =
                    this.resolveNotificationSound(
                        notification
                    );


                this.unreadCount =
                    this.notifications.filter(
                        item =>
                            !item.is_read
                    ).length;


                this.updateBadges();


                this.updatePageUnreadCount();


                this.renderDropdown();


                /*
                 * PLAY SOUND.
                 *
                 * Sound preferences only control
                 * whether the sound is played.
                 *
                 * They do NOT affect delivery.
                 */

                if (sound) {

                    await this.playSound(
                        sound
                    );

                }


                /*
                 * Refresh authoritative
                 * server data.
                 */

                setTimeout(
                    () => {

                        this.loadNotifications();

                    },
                    500
                );

            }
        );


        navigator.serviceWorker.addEventListener(
            "controllerchange",
            () => {

                console.log(
                    "BizTrace service worker controller changed."
                );

            }
        );

    },


    /* ========================================================
       EVENTS
    ======================================================== */

    bindEvents() {

        /*
         * Unlock audio on first user interaction.
         */

        const unlock =
            () => {

                this.unlockAudio();

            };


        document.addEventListener(
            "pointerdown",
            unlock,
            {
                passive:
                    true,

                once:
                    true
            }
        );


        document.addEventListener(
            "keydown",
            unlock,
            {
                passive:
                    true,

                once:
                    true
            }
        );


        document.addEventListener(
            "touchstart",
            unlock,
            {
                passive:
                    true,

                once:
                    true
            }
        );


        /*
         * Mark all as read.
         */

        document
            .querySelectorAll(
                ".mark-all-notifications"
            )
            .forEach(
                button => {

                    button.addEventListener(
                        "click",
                        event => {

                            event.preventDefault();

                            event.stopPropagation();

                            this.markAllAsRead();

                        }
                    );

                }
            );


        const oldMarkAll =
            document.getElementById(
                "markAllNotificationsRead"
            );


        if (oldMarkAll) {

            oldMarkAll.addEventListener(
                "click",
                event => {

                    event.preventDefault();

                    event.stopPropagation();

                    this.markAllAsRead();

                }
            );

        }


        /*
         * Test sound.
         */

        document
            .querySelectorAll(
                "#testNotificationSound"
            )
            .forEach(
                button => {

                    button.addEventListener(
                        "click",
                        async event => {

                            event.preventDefault();

                            event.stopPropagation();


                            await this.unlockAudio();


                            const played =
                                await this.playSound(
                                    "success",
                                    true
                                );


                            if (played) {

                                const original =
                                    button.innerHTML;


                                button.innerHTML =
                                    '<i class="bi bi-check-circle me-1"></i> Sound works';


                                setTimeout(
                                    () => {

                                        button.innerHTML =
                                            original;

                                    },
                                    2000
                                );

                            } else {

                                button.innerHTML =
                                    '<i class="bi bi-x-circle me-1"></i> Sound failed';

                            }

                        }
                    );

                }
            );


        /*
         * Enable push.
         */

        const pushButton =
            document.getElementById(
                "enablePushNotifications"
            );


        if (pushButton) {

            pushButton.addEventListener(
                "click",
                async event => {

                    event.preventDefault();

                    event.stopPropagation();

                    await this.enablePush();

                }
            );

        }


        /*
         * Notification click.
         */

        document.addEventListener(
            "click",
            async event => {

                const item =
                    event.target.closest(
                        "[data-notification-id]"
                    );


                if (!item) {

                    return;

                }


                const id =
                    item.getAttribute(
                        "data-notification-id"
                    );


                if (!id) {

                    return;

                }


                if (
                    !item.matches(
                        "a.notification-page-item, a.notification-dropdown-item"
                    )
                ) {

                    return;

                }


                event.preventDefault();


                await this.unlockAudio();


                await this.markAsRead(
                    id
                );


                const destination =
                    item.getAttribute(
                        "href"
                    );


                if (destination) {

                    window.location.href =
                        destination;

                }

            }
        );

    },


    /* ========================================================
       LOAD NOTIFICATIONS
    ======================================================== */

    async loadNotifications(
        options = {}
    ) {

        try {

            const response =
                await fetch(
                    "/notifications/api/recent",
                    {
                        method:
                            "GET",

                        credentials:
                            "same-origin",

                        headers: {
                            "Accept":
                                "application/json"
                        },

                        cache:
                            "no-store"
                    }
                );


            if (!response.ok) {

                console.error(
                    "Unable to load notifications:",
                    response.status
                );


                return;

            }


            const data =
                await response.json();


            if (!data.success) {

                console.error(
                    "Notification API returned failure:",
                    data
                );


                return;

            }


            /*
             * IDs currently in browser.
             */

            const previousIds =
                new Set(
                    this.notifications.map(
                        notification =>
                            String(
                                notification.id
                            )
                    )
                );


            /*
             * Server notifications.
             */

            const serverNotifications =
                Array.isArray(
                    data.notifications
                )
                    ? data.notifications
                    : [];


            /*
             * Existing notifications do not
             * play sounds on first load.
             */

            let newNotifications =
                [];


            if (
                this.initialLoadComplete
            ) {

                newNotifications =
                    serverNotifications.filter(
                        notification =>
                            !previousIds.has(
                                String(
                                    notification.id
                                )
                            )
                    );

            }


            /*
             * Update server list.
             */

            this.notifications =
                serverNotifications;


            /*
             * Server unread count is authoritative.
             */

            this.unreadCount =
                Number(
                    data.unread_count || 0
                );


            /*
             * Sound preferences.
             */

            if (
                data.sound_preferences
            ) {

                this.soundPreferences = {

                    ...this.soundPreferences,

                    ...data.sound_preferences

                };

            }


            /*
             * Initial load.
             */

            if (
                !this.initialLoadComplete
            ) {

                this.knownNotificationIds =
                    new Set(
                        this.notifications.map(
                            notification =>
                                String(
                                    notification.id
                                )
                        )
                    );


                this.initialLoadComplete =
                    true;

            }


            /*
             * UI.
             */

            this.updateBadges();


            this.renderDropdown();


            this.updatePageUnreadCount();


            this.updateRelativeTimes();


            /*
             * PLAY SOUNDS FOR NEW NOTIFICATIONS.
             */

            if (
                newNotifications.length > 0
            ) {

                console.log(
                    "BizTrace newly detected notifications:",
                    newNotifications
                );


                /*
                 * Process oldest first.
                 */

                const ordered =
                    [...newNotifications]
                        .reverse();


                for (
                    const notification
                    of ordered
                ) {

                    const id =
                        String(
                            notification.id
                        );


                    this.knownNotificationIds.add(
                        id
                    );


                    const sound =
                        this.resolveNotificationSound(
                            notification
                        );


                    if (sound) {

                        console.log(
                            "BizTrace polling sound:",
                            sound,
                            notification
                        );


                        await this.playSound(
                            sound
                        );

                    }

                }

            }


            /*
             * Explicit sound request.
             */

            if (
                options.playSound === true &&
                options.sound
            ) {

                await this.playSound(
                    options.sound
                );

            }

        } catch (error) {

            console.error(
                "Notification loading failed:",
                error
            );

        }

    },


    /* ========================================================
       DROPDOWN
    ======================================================== */

    renderDropdown() {

        const container =
            document.getElementById(
                "notificationList"
            );


        if (!container) {

            return;

        }


        if (
            !this.notifications.length
        ) {

            container.innerHTML = `

                <div class="notification-dropdown-empty">

                    <div class="notification-dropdown-empty-icon">

                        <i class="bi bi-bell-slash"></i>

                    </div>

                    <strong>
                        No notifications
                    </strong>

                    <span>
                        You're all caught up.
                    </span>

                </div>

            `;


            return;

        }


        container.innerHTML =
            this.notifications
                .map(
                    notification =>
                        this.renderNotificationItem(
                            notification
                        )
                )
                .join("");

    },


    /* ========================================================
       NOTIFICATION ITEM
       
       IMPORTANT:
       Icons are based ONLY on delivery category.
       
       Sound types are NOT used as categories.
    ======================================================== */

    renderNotificationItem(
        notification
    ) {

        const id =
            String(
                notification.id
            );


        const unread =
            !notification.is_read;


        let icon =
            "bi-info-circle-fill";


        const category =
            String(
                notification.category ||
                ""
            )
                .trim()
                .toLowerCase()
                .replace(
                    /-/g,
                    "_"
                );


        switch (
            category
        ) {

            case "sale":

                icon =
                    "bi-cart-check-fill";

                break;


            case "payment":

                icon =
                    "bi-credit-card-fill";

                break;


            case "purchase":

                icon =
                    "bi-bag-fill";

                break;


            case "inventory":

                icon =
                    "bi-box-seam-fill";

                break;


            case "expense":

                icon =
                    "bi-wallet2";

                break;


            case "cash_deposit":

                icon =
                    "bi-bank2";

                break;


            case "receivable":

                icon =
                    "bi-arrow-down-circle-fill";

                break;


            case "payable":

                icon =
                    "bi-arrow-up-circle-fill";

                break;


            case "financial":

                icon =
                    "bi-graph-up-arrow";

                break;


            case "security":

                icon =
                    "bi-shield-lock-fill";

                break;


            default:

                icon =
                    "bi-info-circle-fill";

        }


        const detailsUrl =
            notification.details_url ||
            `/notifications/${id}`;


        /*
         * Sound label is optional and is purely
         * informational in the dropdown.
         */

        const sound =
            this.resolveNotificationSound(
                notification
            );


        let soundLabel = "";


        if (sound) {

            const soundLabels = {

                success:
                    "Success sound",

                system:
                    "System sound",

                error:
                    "Error sound",

                "low-stock":
                    "Low stock sound",

                "gross-loss":
                    "Gross loss sound",

                "net-loss":
                    "Net loss sound"

            };


            soundLabel =
                soundLabels[
                    sound
                ] || "";

        }


        return `

            <a
                href="${this.escapeHtml(
                    detailsUrl
                )}"
                class="notification-dropdown-item ${
                    unread
                        ? "unread"
                        : ""
                }"
                data-notification-id="${this.escapeHtml(
                    id
                )}"
            >

                <div
                    class="notification-dropdown-icon ${this.escapeHtml(
                        category ||
                        "system"
                    )}"
                >

                    <i
                        class="bi ${icon}"
                    ></i>

                </div>


                <div
                    class="notification-dropdown-content"
                >

                    <strong>
                        ${this.escapeHtml(
                            notification.title ||
                            "BizTrace IMS"
                        )}
                    </strong>


                    <span>
                        ${this.escapeHtml(
                            notification.message ||
                            ""
                        )}
                    </span>


                    <small
                        data-notification-time="${this.escapeHtml(
                            notification.created_at ||
                            ""
                        )}"
                    >
                        ${this.formatRelativeTime(
                            notification.created_at
                        )}
                    </small>


                    ${
                        soundLabel

                        ? `

                            <small
                                class="notification-sound-label"
                            >
                                <i class="bi bi-volume-up me-1"></i>
                                ${this.escapeHtml(
                                    soundLabel
                                )}
                            </small>

                        `

                        : ""
                    }

                </div>


                <div
                    class="notification-dropdown-status"
                >

                    ${
                        unread

                        ? `

                            <span
                                class="notification-dropdown-dot"
                            ></span>

                        `

                        : `

                            <i
                                class="bi bi-check2 notification-read-icon"
                            ></i>

                        `
                    }

                </div>

            </a>

        `;

    },


    /* ========================================================
       MARK ONE AS READ
    ======================================================== */

    async markAsRead(
        notificationId
    ) {

        try {

            const response =
                await fetch(
                    `/notifications/${notificationId}/read`,
                    {
                        method:
                            "POST",

                        credentials:
                            "same-origin",

                        headers: {
                            "Accept":
                                "application/json"
                        }
                    }
                );


            if (!response.ok) {

                console.error(
                    "Unable to mark notification as read:",
                    response.status
                );


                return false;

            }


            const data =
                await response.json();


            if (!data.success) {

                return false;

            }


            const notification =
                this.notifications.find(
                    item =>
                        String(
                            item.id
                        ) ===
                        String(
                            notificationId
                        )
                );


            if (
                notification &&
                !notification.is_read
            ) {

                notification.is_read =
                    true;

            }


            this.unreadCount =
                Number(
                    data.unread_count ??
                    Math.max(
                        0,
                        this.unreadCount - 1
                    )
                );


            this.updateBadges();


            this.updatePageUnreadCount();


            this.updateNotificationDom(
                notificationId,
                true
            );


            return true;

        } catch (error) {

            console.error(
                "Unable to mark notification as read:",
                error
            );


            return false;

        }

    },


    /* ========================================================
       MARK ALL AS READ
    ======================================================== */

    async markAllAsRead() {

        try {

            const response =
                await fetch(
                    "/notifications/mark-all-read",
                    {
                        method:
                            "POST",

                        credentials:
                            "same-origin",

                        headers: {
                            "Accept":
                                "application/json"
                        }
                    }
                );


            if (!response.ok) {

                console.error(
                    "Unable to mark all notifications as read:",
                    response.status
                );


                return;

            }


            const data =
                await response.json();


            if (!data.success) {

                return;

            }


            this.notifications.forEach(
                notification => {

                    notification.is_read =
                        true;

                }
            );


            this.unreadCount =
                Number(
                    data.unread_count || 0
                );


            this.updateBadges();


            this.updatePageUnreadCount();


            this.updateAllNotificationDom();


            this.renderDropdown();

        } catch (error) {

            console.error(
                "Mark-all-read failed:",
                error
            );

        }

    },


    /* ========================================================
       UPDATE ONE DOM ITEM
    ======================================================== */

    updateNotificationDom(
        notificationId,
        isRead
    ) {

        document
            .querySelectorAll(
                "[data-notification-id]"
            )
            .forEach(
                element => {

                    if (
                        String(
                            element.getAttribute(
                                "data-notification-id"
                            )
                        ) !==
                        String(
                            notificationId
                        )
                    ) {

                        return;

                    }


                    if (isRead) {

                        element.classList.remove(
                            "unread"
                        );


                        element
                            .querySelectorAll(
                                ".notification-page-dot, .notification-dropdown-dot, .notification-unread-label"
                            )
                            .forEach(
                                child =>
                                    child.remove()
                            );


                        if (
                            element.classList.contains(
                                "notification-dropdown-item"
                            )
                        ) {

                            const status =
                                element.querySelector(
                                    ".notification-dropdown-status"
                                );


                            if (status) {

                                status.innerHTML =
                                    '<i class="bi bi-check2 notification-read-icon"></i>';

                            }

                        }

                    }

                }
            );

    },


    /* ========================================================
       UPDATE ALL DOM ITEMS
    ======================================================== */

    updateAllNotificationDom() {

        document
            .querySelectorAll(
                "[data-notification-id]"
            )
            .forEach(
                element => {

                    element.classList.remove(
                        "unread"
                    );


                    element
                        .querySelectorAll(
                            ".notification-page-dot, .notification-dropdown-dot, .notification-unread-label"
                        )
                        .forEach(
                            child =>
                                child.remove()
                        );


                    if (
                        element.classList.contains(
                            "notification-dropdown-item"
                        )
                    ) {

                        const status =
                            element.querySelector(
                                ".notification-dropdown-status"
                            );


                        if (status) {

                            status.innerHTML =
                                '<i class="bi bi-check2 notification-read-icon"></i>';

                        }

                    }

                }
            );

    },


    /* ========================================================
       BADGES
    ======================================================== */

    updateBadges() {

        const badges =
            document.querySelectorAll(
                "#topNotificationBadge, #sidebarNotificationBadge"
            );


        badges.forEach(
            badge => {

                if (
                    this.unreadCount > 0
                ) {

                    badge.textContent =
                        this.unreadCount > 99
                            ? "99+"
                            : this.unreadCount;


                    badge.style.display =
                        "flex";

                } else {

                    badge.textContent =
                        "";


                    badge.style.display =
                        "none";

                }

            }
        );


        const unreadText =
            document.getElementById(
                "notificationUnreadText"
            );


        if (unreadText) {

            unreadText.textContent =
                this.unreadCount === 1
                    ? "1 unread"
                    : `${this.unreadCount} unread`;

        }

    },


    /* ========================================================
       PAGE UNREAD COUNT
    ======================================================== */

    updatePageUnreadCount() {

        const element =
            document.getElementById(
                "notificationPageUnreadCount"
            );


        if (element) {

            element.textContent =
                this.unreadCount;

        }

    },


    /* ========================================================
       SERVICE WORKER
    ======================================================== */

    async registerServiceWorker() {

        if (
            !("serviceWorker" in navigator)
        ) {

            console.warn(
                "Service workers are not supported."
            );


            return null;

        }


        try {

            this.serviceWorkerRegistration =
                await navigator.serviceWorker.register(
                    "/service-worker.js",
                    {
                        scope:
                            "/"
                    }
                );


            console.log(
                "BizTrace service worker registered:",
                this.serviceWorkerRegistration.scope
            );


            await navigator.serviceWorker.ready;


            return this.serviceWorkerRegistration;

        } catch (error) {

            console.error(
                "Service worker registration failed:",
                error
            );


            return null;

        }

    },


    /* ========================================================
       PUSH SUBSCRIPTION STATE
    ======================================================== */

    async syncPushSubscriptionState() {

        try {

            if (
                !("serviceWorker" in navigator)
            ) {

                return false;

            }


            const registration =
                this.serviceWorkerRegistration ||
                await navigator.serviceWorker.ready;


            if (!registration) {

                return false;

            }


            const subscription =
                await registration
                    .pushManager
                    .getSubscription();


            if (subscription) {

                this.pushSubscription =
                    subscription;


                this.pushEnabled =
                    true;


                this.pushStateChecked =
                    true;


                if (
                    "Notification" in window &&
                    Notification.permission ===
                    "granted"
                ) {

                    await this.savePushSubscription(
                        subscription,
                        false
                    );

                }


                return true;

            }


            this.pushSubscription =
                null;


            this.pushEnabled =
                false;


            this.pushStateChecked =
                true;


            return false;

        } catch (error) {

            console.error(
                "Push subscription state check failed:",
                error
            );


            this.pushStateChecked =
                true;


            return false;

        }

    },


    /* ========================================================
       SAVE PUSH SUBSCRIPTION
    ======================================================== */

    async savePushSubscription(
        subscription,
        showMessage = false
    ) {

        if (!subscription) {

            return false;

        }


        try {

            const response =
                await fetch(
                    "/notifications/api/push/subscribe",
                    {
                        method:
                            "POST",

                        credentials:
                            "same-origin",

                        headers: {

                            "Content-Type":
                                "application/json",

                            "Accept":
                                "application/json"

                        },

                        body:
                            JSON.stringify(
                                subscription.toJSON()
                            )

                    }
                );


            if (!response.ok) {

                console.error(
                    "Push subscription sync failed:",
                    response.status
                );


                return false;

            }


            const data =
                await response.json();


            if (!data.success) {

                return false;

            }


            this.pushSubscription =
                subscription;


            this.pushEnabled =
                true;


            if (showMessage) {

                alert(
                    "Browser notifications have been enabled."
                );

            }


            return true;

        } catch (error) {

            console.error(
                "Push subscription synchronization failed:",
                error
            );


            return false;

        }

    },


    /* ========================================================
       ENABLE PUSH
    ======================================================== */

    async enablePush() {

        if (
            !("Notification" in window)
        ) {

            alert(
                "This browser does not support browser notifications."
            );


            return;

        }


        try {

            await this.unlockAudio();


            const permission =
                await Notification.requestPermission();


            if (
                permission !==
                "granted"
            ) {

                await this.updatePushButton();


                alert(
                    "Browser notification permission was not granted."
                );


                return;

            }


            const registration =
                this.serviceWorkerRegistration ||
                await navigator.serviceWorker.ready;


            if (!registration) {

                throw new Error(
                    "Service worker registration is unavailable."
                );

            }


            const publicKeyResponse =
                await fetch(
                    "/notifications/api/push/public-key",
                    {
                        credentials:
                            "same-origin",

                        headers: {
                            "Accept":
                                "application/json"
                        },

                        cache:
                            "no-store"
                    }
                );


            if (
                !publicKeyResponse.ok
            ) {

                throw new Error(
                    `Unable to obtain VAPID public key: ${publicKeyResponse.status}`
                );

            }


            const publicKeyData =
                await publicKeyResponse.json();


            if (
                !publicKeyData.success ||
                !publicKeyData.public_key
            ) {

                throw new Error(
                    publicKeyData.message ||
                    "VAPID public key is missing."
                );

            }


            let subscription =
                await registration
                    .pushManager
                    .getSubscription();


            if (!subscription) {

                subscription =
                    await registration
                        .pushManager
                        .subscribe(
                            {
                                userVisibleOnly:
                                    true,

                                applicationServerKey:
                                    this.urlBase64ToUint8Array(
                                        publicKeyData.public_key
                                    )
                            }
                        );

            }


            const saved =
                await this.savePushSubscription(
                    subscription,
                    false
                );


            if (!saved) {

                throw new Error(
                    "The push subscription could not be saved."
                );

            }


            this.pushSubscription =
                subscription;


            this.pushEnabled =
                true;


            await this.updatePushButton();


            alert(
                "Browser notifications have been enabled."
            );

        } catch (error) {

            console.error(
                "Push notification setup failed:",
                error
            );


            await this.updatePushButton();


            alert(
                `Unable to enable browser notifications.\n\n${error.message}`
            );

        }

    },


    /* ========================================================
       PUSH BUTTON
    ======================================================== */

    async updatePushButton() {

        const button =
            document.getElementById(
                "enablePushNotifications"
            );


        if (!button) {

            return;

        }


        if (
            !("Notification" in window)
        ) {

            button.innerHTML =
                '<i class="bi bi-bell-slash me-1"></i> Notifications unsupported';


            button.disabled =
                true;


            return;

        }


        const permission =
            Notification.permission;


        let subscription =
            this.pushSubscription;


        if (
            !subscription &&
            "serviceWorker" in navigator
        ) {

            try {

                const registration =
                    this.serviceWorkerRegistration ||
                    await navigator.serviceWorker.ready;


                subscription =
                    await registration
                        .pushManager
                        .getSubscription();


                if (subscription) {

                    this.pushSubscription =
                        subscription;


                    this.pushEnabled =
                        true;

                }

            } catch (error) {

                console.warn(
                    "Unable to check push subscription:",
                    error
                );

            }

        }


        if (
            permission === "granted" &&
            subscription
        ) {

            button.innerHTML =
                '<i class="bi bi-bell-fill me-1"></i> Browser notifications enabled';


            button.classList.remove(
                "btn-light",
                "btn-secondary",
                "btn-warning"
            );


            button.classList.add(
                "btn-success"
            );


            button.disabled =
                false;


            return;

        }


        if (
            permission === "denied"
        ) {

            button.innerHTML =
                '<i class="bi bi-bell-slash me-1"></i> Notifications blocked';


            button.classList.remove(
                "btn-success",
                "btn-light"
            );


            button.classList.add(
                "btn-warning"
            );


            button.disabled =
                false;


            return;

        }


        button.innerHTML =
            '<i class="bi bi-bell me-1"></i> Enable browser notifications';


        button.classList.remove(
            "btn-success",
            "btn-secondary",
            "btn-warning"
        );


        button.classList.add(
            "btn-light"
        );


        button.disabled =
            false;

    },


    /* ========================================================
       BASE64
    ======================================================== */

    urlBase64ToUint8Array(
        base64String
    ) {

        const padding =
            "=".repeat(
                (
                    4 -
                    (
                        base64String.length %
                        4
                    )
                ) % 4
            );


        const base64 =
            (
                base64String +
                padding
            )
                .replace(
                    /-/g,
                    "+"
                )
                .replace(
                    /_/g,
                    "/"
                );


        const rawData =
            window.atob(
                base64
            );


        return Uint8Array.from(
            [...rawData].map(
                char =>
                    char.charCodeAt(0)
            )
        );

    },


    /* ========================================================
       RELATIVE TIME
    ======================================================== */

    formatRelativeTime(
        dateString
    ) {

        if (!dateString) {

            return "";

        }


        const date =
            new Date(
                dateString
            );


        if (
            Number.isNaN(
                date.getTime()
            )
        ) {

            return "";

        }


        const seconds =
            Math.floor(
                (
                    Date.now() -
                    date.getTime()
                ) / 1000
            );


        if (
            seconds < 10
        ) {

            return "Just now";

        }


        if (
            seconds < 60
        ) {

            return `${seconds}s ago`;

        }


        const minutes =
            Math.floor(
                seconds / 60
            );


        if (
            minutes < 60
        ) {

            return `${minutes}m ago`;

        }


        const hours =
            Math.floor(
                minutes / 60
            );


        if (
            hours < 24
        ) {

            return `${hours}h ago`;

        }


        const days =
            Math.floor(
                hours / 24
            );


        if (
            days < 7
        ) {

            return `${days}d ago`;

        }


        return date.toLocaleDateString(
            undefined,
            {
                day:
                    "numeric",

                month:
                    "short",

                year:
                    "numeric"
            }
        );

    },


    /* ========================================================
       UPDATE TIMES
    ======================================================== */

    updateRelativeTimes() {

        document
            .querySelectorAll(
                "[data-notification-time]"
            )
            .forEach(
                element => {

                    const value =
                        element.getAttribute(
                            "data-notification-time"
                        );


                    if (!value) {

                        return;

                    }


                    element.textContent =
                        this.formatRelativeTime(
                            value
                        );

                }
            );

    },


    /* ========================================================
       ESCAPE HTML
    ======================================================== */

    escapeHtml(
        value
    ) {

        const div =
            document.createElement(
                "div"
            );


        div.textContent =
            value == null
                ? ""
                : String(value);


        return div.innerHTML;

    }

};


/* ============================================================
   START NOTIFICATION MANAGER
============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        NotificationManager.init();

    }
);