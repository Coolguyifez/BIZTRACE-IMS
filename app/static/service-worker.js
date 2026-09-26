const CACHE_NAME = "bizflow-ims-v3";


/* ============================================================
   STATIC ASSETS
============================================================ */

const STATIC_ASSETS = [

    "/",

    "/offline",

    "/static/manifest.json",

    "/static/css/style.css",

    "/static/js/app.js",

    /*
     * PWA icons
     */
    "/static/icons/3.png",
    "/static/icons/4.png",
    "/static/icons/5.png",
    "/static/icons/6.png",
    "/static/icons/9.png",
    "/static/icons/7.png",
    "/static/icons/8.png",
    "/static/icons/1.png"

];


/* ============================================================
   INSTALL
============================================================ */

self.addEventListener(
    "install",
    event => {

        console.log(
            "BizTrace PWA: service worker installing..."
        );


        event.waitUntil(

            caches
                .open(CACHE_NAME)

                .then(async cache => {

                    console.log(
                        "BizTrace PWA: caching static assets..."
                    );


                    /*
                     * Cache each asset separately.
                     *
                     * If one asset fails, the rest of the
                     * service worker installation continues.
                     */

                    for (
                        const asset
                        of STATIC_ASSETS
                    ) {

                        try {

                            const response =
                                await fetch(
                                    asset,
                                    {
                                        cache:
                                            "no-cache"
                                    }
                                );


                            /*
                             * Only cache complete 200 responses.
                             *
                             * 206 Partial Content must NEVER
                             * be placed in Cache Storage.
                             */

                            if (
                                response.status ===
                                    200 &&
                                response.type ===
                                    "basic"
                            ) {

                                await cache.put(
                                    asset,
                                    response
                                );

                            }
                            else {

                                console.warn(
                                    "BizTrace PWA: asset not cached:",
                                    asset,
                                    "status:",
                                    response.status
                                );

                            }

                        }
                        catch (error) {

                            console.warn(
                                "BizTrace PWA: could not cache:",
                                asset,
                                error
                            );

                        }

                    }

                })

                .then(() => {

                    console.log(
                        "BizTrace PWA: installation complete."
                    );


                    /*
                     * Activate the new worker immediately.
                     */

                    return self.skipWaiting();

                })

        );

    }
);


/* ============================================================
   ACTIVATE
============================================================ */

self.addEventListener(
    "activate",
    event => {

        console.log(
            "BizTrace PWA: service worker activated."
        );


        event.waitUntil(

            caches
                .keys()

                .then(cacheNames => {

                    return Promise.all(

                        cacheNames

                            .filter(
                                cacheName =>
                                    cacheName !==
                                    CACHE_NAME
                            )

                            .map(
                                cacheName => {

                                    console.log(
                                        "BizTrace PWA: deleting old cache:",
                                        cacheName
                                    );


                                    return caches.delete(
                                        cacheName
                                    );

                                }
                            )

                    );

                })

                .then(() => {

                    console.log(
                        "BizTrace PWA: old caches removed."
                    );


                    /*
                     * Immediately control existing
                     * BizTrace pages.
                     */

                    return self.clients.claim();

                })

        );

    }
);


/* ============================================================
   FETCH
============================================================ */

self.addEventListener(
    "fetch",
    event => {

        const request =
            event.request;


        /* ====================================================
           ONLY GET
        ==================================================== */

        /*
         * Never intercept POST, PUT, PATCH or DELETE.
         */

        if (
            request.method !== "GET"
        ) {

            return;

        }


        const url =
            new URL(
                request.url
            );


        /* ====================================================
           SAME ORIGIN ONLY
        ==================================================== */

        /*
         * Do not interfere with external CDN requests,
         * Google Fonts, Bootstrap CDN, etc.
         */

        if (
            url.origin !==
            self.location.origin
        ) {

            return;

        }


        /* ====================================================
           RANGE REQUESTS
        ==================================================== */

        /*
         * IMPORTANT:
         *
         * Audio/video/browser media requests can contain:
         *
         * Range: bytes=0-
         *
         * The server then returns:
         *
         * 206 Partial Content
         *
         * Cache Storage DOES NOT support these partial
         * responses.
         *
         * Therefore we completely bypass the service worker
         * for Range requests.
         */

        if (
            request.headers.has("range")
        ) {

            console.log(
                "BizTrace PWA: bypassing Range request:",
                url.pathname
            );


            return;

        }


        /* ====================================================
           API REQUESTS
        ==================================================== */

        /*
         * APIs should NEVER fall back to an HTML page.
         *
         * We let the network handle them and return a
         * predictable JSON response when offline.
         */

        if (

            url.pathname.startsWith(
                "/api/"
            )

            ||

            url.pathname.startsWith(
                "/notifications/api/"
            )

            ||

            url.pathname.startsWith(
                "/search/api/"
            )

        ) {

            event.respondWith(

                fetch(request)

                    .catch(() => {

                        console.warn(
                            "BizTrace PWA: API unavailable offline:",
                            url.pathname
                        );


                        return new Response(

                            JSON.stringify({

                                success:
                                    false,

                                offline:
                                    true,

                                message:
                                    "You are currently offline.",

                                notifications:
                                    [],

                                unread_count:
                                    0,

                                results:
                                    []

                            }),

                            {

                                status:
                                    200,

                                headers: {

                                    "Content-Type":
                                        "application/json; charset=utf-8",

                                    "X-BizTrace-Offline":
                                        "true"

                                }

                            }

                        );

                    })

            );


            return;

        }


        /* ====================================================
           PAGE NAVIGATION
        ==================================================== */

        if (
            request.mode === "navigate"
        ) {

            event.respondWith(

                fetch(request)

                    .then(response => {

                        /*
                         * ONLY cache complete 200 responses.
                         *
                         * Never cache:
                         *
                         * 206 Partial Content
                         * 204 No Content
                         * 3xx responses
                         * opaque responses
                         */

                        if (

                            response &&

                            response.status ===
                                200 &&

                            response.type ===
                                "basic"

                        ) {

                            const responseClone =
                                response.clone();


                            caches
                                .open(
                                    CACHE_NAME
                                )

                                .then(cache => {

                                    return cache.put(
                                        request,
                                        responseClone
                                    );

                                })

                                .catch(error => {

                                    console.warn(
                                        "BizTrace PWA: page cache failed:",
                                        error
                                    );

                                });

                        }


                        return response;

                    })

                    .catch(() => {

                        console.warn(
                            "BizTrace PWA: offline navigation:",
                            url.pathname
                        );


                        /*
                         * Try the exact page first.
                         */

                        return caches
                            .match(request)

                            .then(
                                cachedResponse => {

                                    if (
                                        cachedResponse
                                    ) {

                                        return cachedResponse;

                                    }


                                    /*
                                     * Fall back to the
                                     * application shell.
                                     */

                                    return caches.match(
                                        "/offline"
                                    );

                                }
                            );

                    })

            );


            return;

        }


        /* ====================================================
           STATIC / NORMAL GET REQUESTS
        ==================================================== */

        event.respondWith(

            caches
                .match(request)

                .then(cachedResponse => {

                    /*
                     * Cache hit.
                     */

                    if (
                        cachedResponse
                    ) {

                        return cachedResponse;

                    }


                    /*
                     * Cache miss.
                     *
                     * Go to the network.
                     */

                    return fetch(request)

                        .then(response => {

                            /*
                             * IMPORTANT:
                             *
                             * Cache ONLY:
                             *
                             * status 200
                             * basic same-origin response
                             *
                             * Never cache 206.
                             */

                            if (

                                response &&

                                response.status ===
                                    200 &&

                                response.type ===
                                    "basic"

                            ) {

                                const responseClone =
                                    response.clone();


                                caches
                                    .open(
                                        CACHE_NAME
                                    )

                                    .then(cache => {

                                        return cache.put(
                                            request,
                                            responseClone
                                        );

                                    })

                                    .catch(error => {

                                        console.warn(
                                            "BizTrace PWA: resource cache failed:",
                                            request.url,
                                            error
                                        );

                                    });

                            }


                            return response;

                        })

                        .catch(() => {

                            console.warn(
                                "BizTrace PWA: resource unavailable offline:",
                                url.pathname
                            );


                            /*
                             * No cached copy and no network.
                             */

                            return new Response(

                                "",

                                {

                                    status:
                                        503,

                                    statusText:
                                        "Offline"

                                }

                            );

                        });

                })

        );

    }
);


/* ============================================================
   NOTIFICATION SOUND RESOLUTION
============================================================ */

function resolveNotificationSound(
    data
) {

    if (
        !data
    ) {

        return null;

    }


    /*
     * Explicit sound supplied by backend.
     */

    if (
        data.sound
    ) {

        return String(
            data.sound
        )
            .toLowerCase()
            .replace(
                /_/g,
                "-"
            );

    }


    /*
     * Resolve sound from notification category.
     */

    const category =

        String(
            data.category || ""
        )
            .toLowerCase()
            .replace(
                /-/g,
                "_"
            );


    const categorySounds = {

        success:
            "success",

        error:
            "error",

        low_stock:
            "low-stock",

        gross_loss:
            "gross-loss",

        net_loss:
            "net-loss"

    };


    return (
        categorySounds[category] ||
        null
    );

}


/* ============================================================
   PUSH NOTIFICATIONS
============================================================ */

self.addEventListener(
    "push",
    event => {

        let data = {};


        /* ====================================================
           PARSE PUSH DATA
        ==================================================== */

        try {

            if (
                event.data
            ) {

                data =
                    event.data.json();

            }

        }

        catch (error) {

            console.error(
                "BizTrace push JSON error:",
                error
            );


            data = {

                title:
                    "BizTrace IMS",

                message:
                    event.data

                        ? event.data.text()

                        : "You have a new notification."

            };

        }


        /* ====================================================
           NOTIFICATION INFORMATION
        ==================================================== */

        const notificationId =
            data.id ||
            Date.now();


        const title =
            data.title ||
            "BizTrace IMS";


        const message =
            data.message ||
            "You have a new notification.";


        const category =
            data.category ||
            "system";


        const priority =
            data.priority ||
            "normal";


        const sound =
            resolveNotificationSound(
                data
            );


        const detailsUrl =
            data.details_url ||
            `/notifications/${notificationId}`;


        console.log(
            "BizTrace push received:",
            {
                ...data,

                resolved_sound:
                    sound

            }
        );


        /* ====================================================
           SEND TO OPEN BIZTRACE TABS
        ==================================================== */

        const notifyOpenPages =

            self.clients
                .matchAll({

                    type:
                        "window",

                    includeUncontrolled:
                        true

                })

                .then(
                    clientList => {

                        clientList.forEach(
                            client => {

                                client.postMessage({

                                    type:
                                        "BIZTRACE_NOTIFICATION",

                                    notification: {

                                        id:
                                            notificationId,

                                        title:
                                            title,

                                        message:
                                            message,

                                        category:
                                            category,

                                        priority:
                                            priority,

                                        sound:
                                            sound,

                                        details_url:
                                            detailsUrl,

                                        link:
                                            data.link ||
                                            null,

                                        created_at:
                                            data.created_at ||

                                            new Date()
                                                .toISOString()

                                    }

                                });

                            }

                        );

                    }

                );


        /* ====================================================
           NATIVE BROWSER NOTIFICATION
        ==================================================== */

        const showNotification =

            self.registration
                .showNotification(

                    title,

                    {

                        body:
                            message,

                        tag:
                            `bizflow-notification-${notificationId}`,

                        renotify:
                            true,

                        silent:
                            false,

                        requireInteraction:
                            priority ===
                            "critical",

                        icon:
                            "/static/icons/7.png",

                        badge:
                            "/static/icons/7.png",

                        data: {

                            id:
                                notificationId,

                            url:
                                detailsUrl,

                            sound:
                                sound,

                            category:
                                category

                        }

                    }

                );


        /* ====================================================
           COMPLETE PUSH EVENT
        ==================================================== */

        event.waitUntil(

            Promise.all([

                notifyOpenPages,

                showNotification

            ])

        );

    }
);


/* ============================================================
   NOTIFICATION CLICK
============================================================ */

self.addEventListener(
    "notificationclick",
    event => {

        event.notification.close();


        const data =
            event.notification.data ||
            {};


        const targetUrl =
            data.url ||
            "/notifications/";


        event.waitUntil(

            self.clients

                .matchAll({

                    type:
                        "window",

                    includeUncontrolled:
                        true

                })

                .then(
                    clientList => {

                        const absoluteUrl =
                            new URL(

                                targetUrl,

                                self.location.origin

                            ).href;


                        /* ====================================
                           FIND EXISTING BIZTRACE WINDOW
                        ==================================== */

                        for (
                            const client
                            of clientList
                        ) {

                            if (

                                client.url.startsWith(
                                    self.location.origin
                                )

                            ) {

                                return client

                                    .navigate(
                                        absoluteUrl
                                    )

                                    .then(
                                        () =>
                                            client.focus()
                                    );

                            }

                        }


                        /* ====================================
                           OPEN NEW WINDOW
                        ==================================== */

                        if (
                            self.clients.openWindow
                        ) {

                            return self.clients
                                .openWindow(
                                    absoluteUrl
                                );

                        }

                    }

                )

        );

    }
);


/* ============================================================
   SERVICE WORKER MESSAGE HANDLER
============================================================ */

self.addEventListener(
    "message",
    event => {

        if (

            event.data &&

            event.data.type ===
                "SKIP_WAITING"

        ) {

            console.log(
                "BizTrace PWA: activating new service worker..."
            );


            self.skipWaiting();

        }

    }
);


/* ============================================================
   SERVICE WORKER ERROR LOGGING
============================================================ */

self.addEventListener(
    "error",
    event => {

        console.error(
            "BizTrace PWA service worker error:",
            event.error || event.message
        );

    }
);


self.addEventListener(
    "unhandledrejection",
    event => {

        console.error(
            "BizTrace PWA unhandled promise rejection:",
            event.reason
        );

    }
);