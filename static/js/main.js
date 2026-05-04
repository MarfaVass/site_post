// Ждём полной загрузки страницы
document.addEventListener('DOMContentLoaded', function () {

    // === Анимация появления карточек при прокрутке ===
    const cards = document.querySelectorAll('.card');

    // Создаём "наблюдателя" за появлением элементов на экране
    const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            // Если элемент появился на экране
            if (entry.isIntersecting) {
                // Берём задержку из атрибута data-delay
                const delay = entry.target.getAttribute('data-delay') || 0;
                
                // Запускаем анимацию с небольшой задержкой для каскадного эффекта
                setTimeout(function () {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, delay * 80); // каждая карточка появляется чуть позже предыдущей

                // Перестаем наблюдать за этой карточкой после анимации
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1 // срабатывает когда 10% карточки видно
    });

    // Начинаем наблюдение за каждой карточкой
    cards.forEach(function (card) {
        // Добавляем плавный переход в CSS
        card.style.transition = 'opacity 0.6s ease, transform 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
        observer.observe(card);
    });


    // === Параллакс-эффект для фоновых свечений при движении мыши ===
    document.addEventListener('mousemove', function (e) {
        const glows = document.querySelectorAll('.bg-glow');
        
        // Вычисляем смещение курсора от центра экрана
        const x = (e.clientX / window.innerWidth - 0.5) * 2;
        const y = (e.clientY / window.innerHeight - 0.5) * 2;

        glows.forEach(function (glow, index) {
            // Каждая свечка двигается с разной скоростью
            const speed = (index + 1) * 15;
            glow.style.transform = 'translate(' + (x * speed) + 'px, ' + (y * speed) + 'px)';
        });
    });


    // === Плавное появление секций при загрузке ===
    const header = document.querySelector('.header');
    const hero = document.querySelector('.hero');

    header.style.opacity = '0';
    header.style.transform = 'translateY(-20px)';
    header.style.transition = 'all 0.8s ease';

    hero.style.opacity = '0';
    hero.style.transform = 'translateY(30px)';
    hero.style.transition = 'all 0.8s ease 0.2s';

    // Запускаем анимацию через небольшую задержку
    setTimeout(function () {
        header.style.opacity = '1';
        header.style.transform = 'translateY(0)';
        hero.style.opacity = '1';
        hero.style.transform = 'translateY(0)';
    }, 100);

});
