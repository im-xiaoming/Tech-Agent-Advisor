(function () {
    const canvas = document.getElementById("auraCanvas");
    const threeCanvas = document.getElementById("threeCanvas");
    const ctx = canvas.getContext("2d");
    const page = document.querySelector(".landing-page");
    const transition = document.getElementById("portalTransition");
    const links = document.querySelectorAll("[data-transition-link]");
    const videos = Array.from(document.querySelectorAll(".landing-video"));
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const themePalettes = [
        {
            particleCore: "rgba(255, 239, 181, 0.62)",
            particleMid: "rgba(110, 229, 202, 0.25)",
            particleEnd: "rgba(110, 229, 202, 0)",
            ring: 0xf4d982,
            accent: 0x78ead0,
            stars: 0xcff7e8,
        },
        {
            particleCore: "rgba(255, 221, 234, 0.66)",
            particleMid: "rgba(255, 148, 196, 0.3)",
            particleEnd: "rgba(255, 148, 196, 0)",
            ring: 0xffc8dd,
            accent: 0xff9ac7,
            stars: 0xffedf5,
        },
    ];

    let width = 0;
    let height = 0;
    let particles = [];
    let frameId = 0;
    let threeFrameId = 0;
    let threeResize = null;
    let applyThreeTheme = null;
    let activeTheme = 0;
    let activeVideoIndex = 0;
    let videoSwitchTimer = 0;

    function resize() {
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        width = window.innerWidth;
        height = window.innerHeight;
        canvas.width = Math.floor(width * ratio);
        canvas.height = Math.floor(height * ratio);
        canvas.style.width = width + "px";
        canvas.style.height = height + "px";
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        createParticles();
    }

    function initThreeScene() {
        if (!threeCanvas || reduceMotion || !window.THREE) return;

        const THREE = window.THREE;
        const renderer = new THREE.WebGLRenderer({
            canvas: threeCanvas,
            alpha: true,
            antialias: true,
            preserveDrawingBuffer: true,
            powerPreference: "high-performance",
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(window.innerWidth, window.innerHeight, false);

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(
            48,
            window.innerWidth / window.innerHeight,
            0.1,
            100
        );
        camera.position.set(0, 0.35, 6.4);

        const group = new THREE.Group();
        scene.add(group);

        const ringMaterial = new THREE.MeshBasicMaterial({
            color: themePalettes[activeTheme].ring,
            transparent: true,
            opacity: 0.36,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
        });
        const jadeMaterial = new THREE.MeshBasicMaterial({
            color: themePalettes[activeTheme].accent,
            transparent: true,
            opacity: 0.26,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
        });

        const ringA = new THREE.Mesh(new THREE.TorusGeometry(1.75, 0.012, 12, 160), ringMaterial);
        const ringB = new THREE.Mesh(new THREE.TorusGeometry(2.32, 0.009, 12, 180), jadeMaterial);
        const ringC = new THREE.Mesh(new THREE.TorusGeometry(1.12, 0.01, 12, 130), ringMaterial.clone());
        ringC.material.opacity = 0.24;

        ringA.rotation.set(1.15, 0.22, 0.1);
        ringB.rotation.set(1.36, -0.2, 0.42);
        ringC.rotation.set(1.02, 0.4, -0.32);
        group.add(ringA, ringB, ringC);

        const starCount = window.innerWidth < 720 ? 120 : 220;
        const positions = new Float32Array(starCount * 3);
        for (let i = 0; i < starCount; i += 1) {
            const radius = 2.2 + Math.random() * 3.8;
            const angle = Math.random() * Math.PI * 2;
            positions[i * 3] = Math.cos(angle) * radius;
            positions[i * 3 + 1] = (Math.random() - 0.5) * 3.6;
            positions[i * 3 + 2] = Math.sin(angle) * radius - 1.2;
        }

        const starGeometry = new THREE.BufferGeometry();
        starGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        const stars = new THREE.Points(
            starGeometry,
            new THREE.PointsMaterial({
                color: themePalettes[activeTheme].stars,
                size: 0.028,
                transparent: true,
                opacity: 0.68,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
            })
        );
        scene.add(stars);

        const clock = new THREE.Clock();

        applyThreeTheme = (themeIndex) => {
            const palette = themePalettes[themeIndex] || themePalettes[0];
            ringMaterial.color.setHex(palette.ring);
            jadeMaterial.color.setHex(palette.accent);
            ringC.material.color.setHex(palette.ring);
            stars.material.color.setHex(palette.stars);
        };

        threeResize = () => {
            const nextWidth = window.innerWidth;
            const nextHeight = window.innerHeight;
            camera.aspect = nextWidth / nextHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(nextWidth, nextHeight, false);
        };

        function animateThree() {
            const elapsed = clock.getElapsedTime();
            group.rotation.y = elapsed * 0.12;
            ringA.rotation.z = elapsed * 0.32;
            ringB.rotation.z = -elapsed * 0.24;
            ringC.rotation.z = elapsed * 0.38;
            stars.rotation.y = elapsed * 0.025;
            stars.rotation.x = Math.sin(elapsed * 0.18) * 0.04;
            renderer.render(scene, camera);
            threeFrameId = window.requestAnimationFrame(animateThree);
        }

        animateThree();
    }

    function scheduleVideoSwitch() {
        if (videoSwitchTimer) window.clearTimeout(videoSwitchTimer);
        const activeVideo = videos[activeVideoIndex];
        const duration = Number.isFinite(activeVideo?.duration) ? activeVideo.duration : 0;
        if (!duration) return;

        const segmentSeconds = Math.max(duration - activeVideo.currentTime + 0.35, 0.35);
        videoSwitchTimer = window.setTimeout(() => {
            activateVideo((activeVideoIndex + 1) % videos.length);
        }, segmentSeconds * 1000);
    }

    function activateVideo(nextIndex) {
        if (!videos.length || nextIndex === activeVideoIndex) return;

        const previousVideo = videos[activeVideoIndex];
        const nextVideo = videos[nextIndex];
        activeVideoIndex = nextIndex;
        activeTheme = nextIndex;

        page.classList.toggle("video-theme-1", nextIndex === 0);
        page.classList.toggle("video-theme-2", nextIndex === 1);
        page.dataset.activeVideo = String(nextIndex + 1);
        if (applyThreeTheme) applyThreeTheme(activeTheme);

        nextVideo.currentTime = 0;
        const playPromise = nextVideo.play();
        if (playPromise && typeof playPromise.catch === "function") {
            playPromise.catch(() => {});
        }

        nextVideo.classList.add("is-active");
        previousVideo.classList.remove("is-active");

        window.setTimeout(() => {
            previousVideo.pause();
            previousVideo.currentTime = 0;
        }, 1200);

        scheduleVideoSwitch();
    }

    function initVideoRotation() {
        if (videos.length < 2) {
            videos[0]?.play?.();
            return;
        }

        videos.forEach((video, index) => {
            video.muted = true;
            video.playsInline = true;
            video.addEventListener("ended", () => {
                if (index === activeVideoIndex) activateVideo((index + 1) % videos.length);
            });
            video.addEventListener("loadedmetadata", () => {
                if (index === activeVideoIndex) scheduleVideoSwitch();
            }, { once: true });
        });

        page.classList.add("video-theme-1");
        videos[0].classList.add("is-active");
        const playPromise = videos[0].play();
        if (playPromise && typeof playPromise.catch === "function") {
            playPromise.catch(() => {});
        }
        scheduleVideoSwitch();
    }

    function createParticles() {
        const count = Math.max(54, Math.floor((width * height) / 22000));
        particles = Array.from({ length: count }, () => ({
            x: Math.random() * width,
            y: Math.random() * height,
            z: 0.35 + Math.random() * 1.4,
            radius: 0.8 + Math.random() * 2.6,
            speed: 0.18 + Math.random() * 0.56,
            drift: -0.24 + Math.random() * 0.48,
            phase: Math.random() * Math.PI * 2,
        }));
    }

    function draw(time) {
        ctx.clearRect(0, 0, width, height);
        ctx.save();
        ctx.globalCompositeOperation = "lighter";

        particles.forEach((particle) => {
            particle.y -= particle.speed * particle.z;
            particle.x += Math.sin(time * 0.001 + particle.phase) * 0.26 + particle.drift;

            if (particle.y < -24) {
                particle.y = height + 24;
                particle.x = Math.random() * width;
            }

            if (particle.x < -24) particle.x = width + 24;
            if (particle.x > width + 24) particle.x = -24;

            const palette = themePalettes[activeTheme] || themePalettes[0];
            const glow = ctx.createRadialGradient(
                particle.x,
                particle.y,
                0,
                particle.x,
                particle.y,
                particle.radius * 9
            );
            glow.addColorStop(0, palette.particleCore);
            glow.addColorStop(0.35, palette.particleMid);
            glow.addColorStop(1, palette.particleEnd);

            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(particle.x, particle.y, particle.radius * 9, 0, Math.PI * 2);
            ctx.fill();
        });

        ctx.restore();
        frameId = window.requestAnimationFrame(draw);
    }

    links.forEach((link) => {
        link.addEventListener("click", (event) => {
            if (reduceMotion) return;

            event.preventDefault();
            const target = link.href;
            page.classList.add("is-transitioning");
            transition.setAttribute("aria-hidden", "false");
            window.setTimeout(() => {
                window.location.href = target;
            }, 760);
        });
    });

    window.addEventListener("resize", () => {
        resize();
        if (threeResize) threeResize();
    });
    resize();
    initVideoRotation();
    initThreeScene();

    if (!reduceMotion) {
        frameId = window.requestAnimationFrame(draw);
    }

    window.addEventListener("pagehide", () => {
        if (frameId) window.cancelAnimationFrame(frameId);
        if (threeFrameId) window.cancelAnimationFrame(threeFrameId);
        if (videoSwitchTimer) window.clearTimeout(videoSwitchTimer);
    });
})();
