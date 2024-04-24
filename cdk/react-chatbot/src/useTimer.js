// useTimer.js
import { useState, useEffect } from 'react';

const useTimer = () => {
  const [elapsedTime, setElapsedTime] = useState(0);
  const [startTime, setStartTime] = useState(null);

  useEffect(() => {
    let intervalId;

    if (startTime !== null) {
      intervalId = setInterval(() => {
        const currentTime = Date.now();
        setElapsedTime(currentTime - startTime);
      }, 100);
    }

    return () => {
      clearInterval(intervalId);
    };
  }, [startTime]);

  const startTimer = () => {
    setStartTime(Date.now());
  };

  const stopTimer = () => {
    setStartTime(null);
  };

  const resetTimer = () => {
    setElapsedTime(0);
    setStartTime(null);
  };

  return { elapsedTime, startTimer, stopTimer, resetTimer };
};

export default useTimer;