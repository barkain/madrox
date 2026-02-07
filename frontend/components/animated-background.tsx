'use client'

import { cn } from '@/lib/utils'

interface AnimatedBackgroundProps {
  /** Additional CSS classes */
  className?: string
  /** Variant of the animation effect (kept for API compat, only 'image' used now) */
  variant?: 'aurora' | 'mesh' | 'beams' | 'particles' | 'image'
  /** Intensity of the effect */
  intensity?: 'subtle' | 'medium' | 'strong'
}

/**
 * AnimatedBackground - Full-screen background using static images
 * that swap between dark and light mode.
 */
export function AnimatedBackground({
  className,
}: AnimatedBackgroundProps) {
  return (
    <div
      className={cn(
        'fixed inset-0 z-[1] overflow-hidden pointer-events-none',
        className
      )}
      aria-hidden="true"
    >
      {/* Dark mode background */}
      <img
        src="/bg-dark.png"
        alt=""
        className="absolute inset-0 w-full h-full object-cover hidden dark:block"
      />
      {/* Light mode background */}
      <img
        src="/bg-light.png"
        alt=""
        className="absolute inset-0 w-full h-full object-cover block dark:hidden"
      />
      {/* Vignette effect for edge blending */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,var(--background)_90%)]" />
    </div>
  )
}

export default AnimatedBackground
