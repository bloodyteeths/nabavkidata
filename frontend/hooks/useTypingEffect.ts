import { useState, useEffect, useCallback } from 'react';

export function useTypingEffect(
    phrases: string[],
    typingSpeed: number = 100,
    deletingSpeed: number = 50,
    pauseDuration: number = 3000
) {
    const [currentPhraseIndex, setCurrentPhraseIndex] = useState(0);
    const [currentText, setCurrentText] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);
    const [isPaused, setIsPaused] = useState(false);

    useEffect(() => {
        if (phrases.length === 0) return;

        const currentPhrase = phrases[currentPhraseIndex];

        if (isPaused) {
            const pauseTimeout = setTimeout(() => {
                setIsPaused(false);
                setIsDeleting(true);
            }, pauseDuration);
            return () => clearTimeout(pauseTimeout);
        }

        if (!isDeleting && currentText === currentPhrase) {
            setIsPaused(true);
            return;
        }

        if (isDeleting && currentText === '') {
            setIsDeleting(false);
            setCurrentPhraseIndex((prev) => (prev + 1) % phrases.length);
            return;
        }

        const timeout = setTimeout(
            () => {
                setCurrentText((prev) => {
                    if (isDeleting) {
                        return currentPhrase.substring(0, prev.length - 1);
                    } else {
                        return currentPhrase.substring(0, prev.length + 1);
                    }
                });
            },
            isDeleting ? deletingSpeed : typingSpeed
        );

        return () => clearTimeout(timeout);
    }, [currentText, isDeleting, isPaused, currentPhraseIndex, phrases, typingSpeed, deletingSpeed, pauseDuration]);

    return currentText;
}
