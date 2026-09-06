/**
 * FlyAsh Manager Multi-Language Localization Engine
 * Supports 12+ Indian Regional Languages with Instant Switching
 */

(function() {
    'use strict';

    // Supported language mappings
    const LANGUAGES = {
        'en': { name: 'English', native: 'English', flag: '🌐', gt: 'en' },
        'hi': { name: 'Hindi', native: 'हिन्दी', flag: '🇮🇳', gt: 'hi' },
        'bho': { name: 'Bhojpuri / Bihari', native: 'भोजपुरी', flag: '🇮🇳', gt: 'bho' },
        'ta': { name: 'Tamil', native: 'தமிழ்', flag: '🇮🇳', gt: 'ta' },
        'ml': { name: 'Malayalam', native: 'മലയാളം', flag: '🇮🇳', gt: 'ml' },
        'te': { name: 'Telugu', native: 'తెలుగు', flag: '🇮🇳', gt: 'te' },
        'kn': { name: 'Kannada', native: 'ಕನ್ನಡ', flag: '🇮🇳', gt: 'kn' },
        'bn': { name: 'Bengali', native: 'বাংলা', flag: '🇮🇳', gt: 'bn' },
        'mr': { name: 'Marathi', native: 'मराठी', flag: '🇮🇳', gt: 'mr' },
        'gu': { name: 'Gujarati', native: 'ગુજરાતી', flag: '🇮🇳', gt: 'gu' },
        'pa': { name: 'Punjabi', native: 'ਪੰਜਾਬੀ', flag: '🇮🇳', gt: 'pa' },
        'or': { name: 'Odia', native: 'ଓଡ଼ିଆ', flag: '🇮🇳', gt: 'or' }
    };

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    function setCookie(name, value, days) {
        let expires = '';
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = '; expires=' + date.toUTCString();
        }
        document.cookie = name + '=' + (value || '') + expires + '; path=/; SameSite=Lax';
    }

    // Set active language and trigger translation
    window.setAppLanguage = function(langCode, reload = true) {
        if (!LANGUAGES[langCode]) {
            langCode = 'en';
        }

        const gtLang = LANGUAGES[langCode].gt || langCode;
        
        // Save preferences
        localStorage.setItem('flyash_language', langCode);
        setCookie('flyash_lang', langCode, 365);
        
        // Google Translate cookie convention
        if (langCode === 'en') {
            setCookie('googtrans', '/en/en', 365);
            setCookie('googtrans', '', -1);
        } else {
            setCookie('googtrans', `/en/${gtLang}`, 365);
        }

        // Notify backend of language change
        fetch(`/auth/set-language/${langCode}`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json'
            }
        }).catch(() => {});

        if (reload) {
            window.location.reload();
        }
    };

    // Initialize Google Translate Widget Hidden Bridge
    window.googleTranslateElementInit = function() {
        if (window.google && window.google.translate) {
            new window.google.translate.TranslateElement({
                pageLanguage: 'en',
                includedLanguages: 'en,hi,bho,ta,ml,te,kn,bn,mr,gu,pa,or',
                autoDisplay: false,
                layout: window.google.translate.TranslateElement.InlineLayout.SIMPLE
            }, 'google_translate_element');
        }
    };

    // Load Google Translate Script asynchronously
    function loadGoogleTranslate() {
        if (!document.getElementById('google-translate-script')) {
            const el = document.createElement('div');
            el.id = 'google_translate_element';
            el.style.display = 'none';
            document.body.appendChild(el);

            const script = document.createElement('script');
            script.id = 'google-translate-script';
            script.type = 'text/javascript';
            script.src = '//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
            document.head.appendChild(script);
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        loadGoogleTranslate();

        // Check active language
        const serverLang = document.documentElement.getAttribute('data-lang') || 'en';
        const savedLang = localStorage.getItem('flyash_language') || getCookie('flyash_lang') || serverLang;
        
        if (serverLang && serverLang !== 'en' && savedLang !== serverLang) {
            localStorage.setItem('flyash_language', serverLang);
            setCookie('flyash_lang', serverLang, 365);
        }

        // Language Switcher dropdown click handlers
        document.querySelectorAll('.lang-select-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const code = this.getAttribute('data-lang-code');
                if (code) {
                    window.setAppLanguage(code, true);
                }
            });
        });
    });
})();
