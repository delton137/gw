"use client";

import { useCallback, useState } from "react";

export default function ObfuscatedEmail() {
  const [revealed, setRevealed] = useState(false);
  const parts = ["info", "genewizard", "net"];

  const handleClick = useCallback(() => {
    if (!revealed) {
      setRevealed(true);
      return;
    }
    window.location.href = `mailto:${parts[0]}@${parts[1]}.${parts[2]}`;
  }, [revealed]);

  if (!revealed) {
    return (
      <button
        onClick={handleClick}
        className="text-accent hover:text-accent-hover underline font-medium cursor-pointer"
      >
        here
      </button>
    );
  }

  return (
    <button
      onClick={handleClick}
      className="text-accent hover:text-accent-hover underline font-medium cursor-pointer"
    >
      {parts[0]}&#64;{parts[1]}.{parts[2]}
    </button>
  );
}
