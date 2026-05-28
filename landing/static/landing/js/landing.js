(function () {
    const canvas = document.getElementById("auraCanvas");
    const ctx = canvas.getContext("2d");
    const page = document.querySelector(".landing-page");
    const transition = document.getElementById("portalTransition");
    const links = document.querySelectorAll("[data-transition-link]");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let particles = [];
    let frameId = 0;

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

            const glow = ctx.createRadialGradient(
                particle.x,
                particle.y,
                0,
                particle.x,
                particle.y,
                particle.radius * 9
            );
            glow.addColorStop(0, "rgba(255, 239, 181, 0.62)");
            glow.addColorStop(0.35, "rgba(110, 229, 202, 0.25)");
            glow.addColorStop(1, "rgba(110, 229, 202, 0)");

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

    window.addEventListener("resize", resize);
    resize();

    if (!reduceMotion) {
        frameId = window.requestAnimationFrame(draw);
    }

    window.addEventListener("pagehide", () => {
        if (frameId) window.cancelAnimationFrame(frameId);
    });
})();
