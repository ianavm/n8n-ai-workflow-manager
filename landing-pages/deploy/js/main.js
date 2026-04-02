        (function() {
            'use strict';

            /* ================================
               THEME TOGGLE (LIGHT / DARK)
               ================================ */
            var themeToggle = document.getElementById('themeToggle');
            var savedTheme = localStorage.getItem('avm-theme');

            if (savedTheme === 'light') {
                document.body.classList.add('light-mode');
                themeToggle.setAttribute('aria-label', 'Switch to dark mode');
            }

            themeToggle.addEventListener('click', function() {
                document.body.classList.toggle('light-mode');
                var isLight = document.body.classList.contains('light-mode');
                localStorage.setItem('avm-theme', isLight ? 'light' : 'dark');
                themeToggle.setAttribute('aria-label', isLight ? 'Switch to dark mode' : 'Switch to light mode');
            });

            /* ================================
               HAMBURGER MOBILE NAV TOGGLE
               ================================ */
            const hamburger = document.getElementById('hamburger');
            const navLinks = document.getElementById('navLinks');

            hamburger.addEventListener('click', function() {
                const isOpen = navLinks.classList.toggle('open');
                hamburger.classList.toggle('open');
                hamburger.setAttribute('aria-expanded', isOpen);
            });

            // Close mobile nav when a link is clicked
            navLinks.querySelectorAll('a').forEach(function(link) {
                link.addEventListener('click', function() {
                    navLinks.classList.remove('open');
                    hamburger.classList.remove('open');
                    hamburger.setAttribute('aria-expanded', 'false');
                });
            });

            /* ================================
               NAV SCROLL EFFECT
               ================================ */
            const nav = document.querySelector('.nav');
            let lastScroll = 0;

            window.addEventListener('scroll', function() {
                const currentScroll = window.pageYOffset;
                if (currentScroll > 50) {
                    nav.classList.add('scrolled');
                } else {
                    nav.classList.remove('scrolled');
                }
                lastScroll = currentScroll;
            }, { passive: true });

            /* ================================
               INTERSECTION OBSERVER FOR REVEAL
               ================================ */
            const revealElements = document.querySelectorAll('.reveal');

            const revealObserver = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('active');
                        revealObserver.unobserve(entry.target);
                    }
                });
            }, {
                threshold: 0.1,
                rootMargin: '0px 0px -60px 0px'
            });

            revealElements.forEach(function(el) {
                revealObserver.observe(el);
            });

            /* ================================
               ANIMATED STAT COUNTERS
               ================================ */
            function animateCounter(element, target, suffix, duration) {
                var start = 0;
                var startTime = null;

                function step(timestamp) {
                    if (!startTime) startTime = timestamp;
                    var progress = Math.min((timestamp - startTime) / duration, 1);
                    // Ease out cubic
                    var eased = 1 - Math.pow(1 - progress, 3);
                    var current = Math.floor(eased * target);
                    element.textContent = current + suffix;
                    if (progress < 1) {
                        requestAnimationFrame(step);
                    } else {
                        element.textContent = target + suffix;
                    }
                }

                requestAnimationFrame(step);
            }

            var statsSection = document.querySelector('.stats');
            var statNumbers = document.querySelectorAll('.stat-number');
            var statData = [
                { target: 50, suffix: '+' },
                { target: 3, suffix: 'x' },
                { target: 98, suffix: '%' },
                { target: 12, suffix: '+' }
            ];
            var statsAnimated = false;

            var statsObserver = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting && !statsAnimated) {
                        statsAnimated = true;
                        statNumbers.forEach(function(el, index) {
                            if (statData[index]) {
                                animateCounter(el, statData[index].target, statData[index].suffix, 1800);
                            }
                        });
                        statsObserver.unobserve(entry.target);
                    }
                });
            }, {
                threshold: 0.3
            });

            if (statsSection) {
                statsObserver.observe(statsSection);
            }

            /* ================================
               SMOOTH SCROLL FOR ANCHOR LINKS
               ================================ */
            document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
                anchor.addEventListener('click', function(e) {
                    var href = this.getAttribute('href');
                    if (href === '#') return;

                    var target = document.querySelector(href);
                    if (target) {
                        e.preventDefault();
                        var navHeight = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nav-height'));
                        var targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight;

                        window.scrollTo({
                            top: targetPosition,
                            behavior: 'smooth'
                        });
                    }
                });
            });

            /* ================================
               UTM PARAMETER CAPTURE
               ================================ */
            function getUTMParams() {
                var params = new URLSearchParams(window.location.search);
                return {
                    utm_source: params.get('utm_source') || '',
                    utm_medium: params.get('utm_medium') || '',
                    utm_campaign: params.get('utm_campaign') || '',
                    utm_term: params.get('utm_term') || '',
                    utm_content: params.get('utm_content') || ''
                };
            }

            /* ================================
               FORM SUBMISSION (NETLIFY FORMS + n8n WEBHOOK)
               ================================ */
            var contactForm = document.getElementById('contactForm');
            if (contactForm) {
                contactForm.addEventListener('submit', function(e) {
                    e.preventDefault();

                    var submitBtn = contactForm.querySelector('.btn-primary');
                    var originalHTML = submitBtn.innerHTML;

                    submitBtn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 1s linear infinite"><circle cx="12" cy="12" r="10" stroke-dasharray="30 70"/></svg> Sending...';
                    submitBtn.disabled = true;

                    var formData = new FormData(contactForm);
                    var utmParams = getUTMParams();

                    fetch('/index.html', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: new URLSearchParams(formData).toString()
                    })
                    .then(function(response) {
                        if (response.ok) {
                            submitBtn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Request Sent!';
                            submitBtn.style.background = 'linear-gradient(135deg, #00D4AA, #6C63FF)';

                            /* Google Ads conversion tracking */
                            gtag('event', 'conversion', {
                                send_to: 'AW-11359193832/qaz_CIfuooccEOiVvqgq',
                                value: 1.0,
                                currency: 'ZAR'
                            });
                            /* GA4 generate_lead event for reporting */
                            gtag('event', 'generate_lead', {
                                currency: 'ZAR',
                                value: 5000
                            });
                            /* Meta Pixel Lead conversion */
                            if (typeof fbq === 'function') {
                                fbq('track', 'Lead', {
                                    currency: 'ZAR',
                                    value: 5000
                                });
                            }

                            /* POST to n8n webhooks for lead capture pipeline */
                            var leadPayload = JSON.stringify({
                                    email: formData.get('email'),
                                    firstName: formData.get('firstName') || '',
                                    lastName: formData.get('lastName') || '',
                                    name: ((formData.get('firstName') || '') + ' ' + (formData.get('lastName') || '')).trim(),
                                    company: formData.get('company'),
                                    phone: '',
                                    message: formData.get('message') || '',
                                    interest: formData.get('interest') || '',
                                    page_url: window.location.href,
                                    utm_source: utmParams.utm_source || 'organic',
                                    utm_medium: utmParams.utm_medium || 'website',
                                    utm_campaign: utmParams.utm_campaign,
                                    utm_term: utmParams.utm_term,
                                    utm_content: utmParams.utm_content
                            });
                            var webhookHeaders = { 'Content-Type': 'application/json' };
                            /* Contact form -> Airtable + email notification */
                            fetch('https://ianimmelman89.app.n8n.cloud/webhook/website-contact-form', {
                                method: 'POST', headers: webhookHeaders, body: leadPayload
                            }).catch(function() {});
                            /* SEO lead capture pipeline */
                            fetch('https://ianimmelman89.app.n8n.cloud/webhook/seo-social/lead-capture', {
                                method: 'POST', headers: webhookHeaders, body: leadPayload
                            }).catch(function() { /* silent -- Netlify already captured */ });

                            contactForm.reset();
                        } else {
                            submitBtn.innerHTML = 'Something went wrong — please try again';
                        }
                        setTimeout(function() {
                            submitBtn.innerHTML = originalHTML;
                            submitBtn.style.background = '';
                            submitBtn.disabled = false;
                        }, 3000);
                    })
                    .catch(function() {
                        submitBtn.innerHTML = 'Network error — please try again';
                        setTimeout(function() {
                            submitBtn.innerHTML = originalHTML;
                            submitBtn.style.background = '';
                            submitBtn.disabled = false;
                        }, 3000);
                    });
                });
            }

            /* ================================
               SUPPORT FORM SUBMISSION (SELF-HEALING WEBHOOK)
               ================================ */
            var supportForm = document.getElementById('supportForm');
            var supportSuccess = document.getElementById('supportSuccess');
            if (supportForm) {
                supportForm.addEventListener('submit', function(e) {
                    e.preventDefault();

                    var submitBtn = supportForm.querySelector('.btn-primary');
                    var originalHTML = submitBtn.innerHTML;
                    submitBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 1s linear infinite"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> Sending...';
                    submitBtn.disabled = true;

                    var payload = JSON.stringify({
                        error_message: supportForm.querySelector('[name="error_message"]').value,
                        workflow_name: supportForm.querySelector('[name="workflow_name"]').value || 'Client Report',
                        error_node: 'Client Report',
                        source: 'website',
                        reporter_name: supportForm.querySelector('[name="name"]').value,
                        reporter_email: supportForm.querySelector('[name="email"]').value,
                        priority: supportForm.querySelector('[name="priority"]').value,
                        submitted_at: new Date().toISOString()
                    });

                    fetch('https://ianimmelman89.app.n8n.cloud/webhook/self-healing/report', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: payload
                    })
                    .then(function(resp) {
                        if (resp.ok) {
                            supportForm.style.display = 'none';
                            supportSuccess.classList.add('show');
                        } else {
                            submitBtn.innerHTML = 'Something went wrong. Please email us instead.';
                        }
                        setTimeout(function() {
                            submitBtn.innerHTML = originalHTML;
                            submitBtn.disabled = false;
                        }, 4000);
                    })
                    .catch(function() {
                        submitBtn.innerHTML = 'Network error. Please email admin@anyvisionmedia.com';
                        setTimeout(function() {
                            submitBtn.innerHTML = originalHTML;
                            submitBtn.disabled = false;
                        }, 4000);
                    });
                });
            }

            /* ================================
               KEYBOARD ACCESSIBILITY
               ================================ */
            document.addEventListener('keydown', function(e) {
                // Close mobile nav on Escape
                if (e.key === 'Escape' && navLinks.classList.contains('open')) {
                    navLinks.classList.remove('open');
                    hamburger.classList.remove('open');
                    hamburger.setAttribute('aria-expanded', 'false');
                    hamburger.focus();
                }
            });

        })();
