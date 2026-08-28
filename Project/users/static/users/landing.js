(function () {
    "use strict";

    const nav = document.getElementById("site-nav");
    const menuButton = document.getElementById("mobile-menu");
    const navLinks = document.getElementById("nav-links");
    const scene = document.getElementById("tilt-scene");
    const particleField = document.getElementById("particle-field");

    if (nav) {
        const updateNav = function () {
            nav.classList.toggle("scrolled", window.scrollY > 18);
        };
        updateNav();
        window.addEventListener("scroll", updateNav, { passive: true });
    }

    if (menuButton && navLinks) {
        menuButton.addEventListener("click", function () {
            const open = navLinks.classList.toggle("open");
            menuButton.setAttribute("aria-expanded", String(open));
            menuButton.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
        });

        navLinks.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                navLinks.classList.remove("open");
                menuButton.setAttribute("aria-expanded", "false");
                menuButton.setAttribute("aria-label", "Open navigation");
            });
        });
    }

    const revealItems = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(function (entries, currentObserver) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-visible");
                currentObserver.unobserve(entry.target);
            });
        }, { threshold: 0.12, rootMargin: "0px 0px -30px" });
        revealItems.forEach(function (item) { observer.observe(item); });
    } else {
        revealItems.forEach(function (item) { item.classList.add("is-visible"); });
    }

    const counters = document.querySelectorAll("[data-count]");
    const animateCounter = function (element) {
        const target = Number(element.dataset.count || 0);
        const duration = 850;
        const started = performance.now();
        const tick = function (now) {
            const progress = Math.min(1, (now - started) / duration);
            const eased = 1 - Math.pow(1 - progress, 3);
            element.textContent = String(Math.round(target * eased));
            if (progress < 1) window.requestAnimationFrame(tick);
        };
        window.requestAnimationFrame(tick);
    };

    if ("IntersectionObserver" in window && counters.length) {
        const counterObserver = new IntersectionObserver(function (entries, currentObserver) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                animateCounter(entry.target);
                currentObserver.unobserve(entry.target);
            });
        }, { threshold: 0.65 });
        counters.forEach(function (counter) { counterObserver.observe(counter); });
    } else {
        counters.forEach(function (counter) { counter.textContent = counter.dataset.count; });
    }

    if (scene && window.matchMedia && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        if (particleField) {
            const palette = ["#8b7cff", "#5acbff", "#f17bd2", "#5be0ae"];
            const fragment = document.createDocumentFragment();
            for (let index = 0; index < 28; index += 1) {
                const particle = document.createElement("span");
                particle.className = "particle";
                particle.style.left = `${6 + Math.random() * 88}%`;
                particle.style.top = `${7 + Math.random() * 82}%`;
                particle.style.setProperty("--size", `${1 + Math.random() * 3}px`);
                particle.style.setProperty("--depth", `${20 + Math.round(Math.random() * 100)}px`);
                particle.style.setProperty("--opacity", `${0.26 + Math.random() * 0.62}`);
                particle.style.setProperty("--duration", `${4.5 + Math.random() * 5}s`);
                particle.style.setProperty("--delay", `${Math.random() * -6}s`);
                particle.style.setProperty("--particle-color", palette[index % palette.length]);
                fragment.appendChild(particle);
            }
            particleField.appendChild(fragment);
        }

        const resetTilt = function () {
            scene.style.setProperty("--rx", "8deg");
            scene.style.setProperty("--ry", "-13deg");
            scene.style.setProperty("--mx", "50%");
            scene.style.setProperty("--my", "45%");
        };
        scene.addEventListener("pointermove", function (event) {
            const bounds = scene.getBoundingClientRect();
            const x = (event.clientX - bounds.left) / bounds.width - 0.5;
            const y = (event.clientY - bounds.top) / bounds.height - 0.5;
            scene.style.setProperty("--rx", `${8 - y * 8}deg`);
            scene.style.setProperty("--ry", `${-13 + x * 13}deg`);
            scene.style.setProperty("--mx", `${(x + 0.5) * 100}%`);
            scene.style.setProperty("--my", `${(y + 0.5) * 100}%`);
        });
        scene.addEventListener("pointerleave", resetTilt);
        resetTilt();
    } else if (particleField) {
        particleField.remove();
    }

    if (window.matchMedia && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        document.querySelectorAll(".feature-card, .workflow-step, .why-card").forEach(function (card) {
            card.addEventListener("pointermove", function (event) {
                const bounds = card.getBoundingClientRect();
                const x = (event.clientX - bounds.left) / bounds.width - 0.5;
                const y = (event.clientY - bounds.top) / bounds.height - 0.5;
                card.style.transform = `perspective(850px) rotateX(${-y * 3.8}deg) rotateY(${x * 4.8}deg) translateY(-4px)`;
            });
            card.addEventListener("pointerleave", function () {
                card.style.transform = "";
            });
        });
    }
})();
