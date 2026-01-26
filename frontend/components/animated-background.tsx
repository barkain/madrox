'use client'

import { cn } from '@/lib/utils'

interface AnimatedBackgroundProps {
  /** Additional CSS classes */
  className?: string
  /** Variant of the animation effect */
  variant?: 'aurora' | 'mesh' | 'beams' | 'particles'
  /** Intensity of the effect */
  intensity?: 'subtle' | 'medium' | 'strong'
}

/**
 * AnimatedBackground - A dynamic animated background component
 *
 * Features:
 * - Aurora: Flowing northern lights effect
 * - Mesh: Animated gradient mesh with movement
 * - Beams: Glowing light beams
 * - Particles: Floating particle dots
 *
 * All variants support light and dark themes
 */
export function AnimatedBackground({
  className,
  variant = 'aurora',
  intensity = 'medium',
}: AnimatedBackgroundProps) {
  const intensityConfig = {
    subtle: { opacity: 'opacity-60 dark:opacity-50', blur: 'blur-3xl' },
    medium: { opacity: 'opacity-100', blur: 'blur-xl' },
    strong: { opacity: 'opacity-100 dark:opacity-90', blur: 'blur-xl' },
  }

  const config = intensityConfig[intensity]

  // Aurora variant - flowing northern lights effect
  if (variant === 'aurora') {
    return (
      <div
        className={cn(
          'fixed inset-0 z-[1] overflow-hidden pointer-events-none',
          className
        )}
        aria-hidden="true"
      >
        {/* Aurora layers */}
        <div
          className={cn(
            'absolute inset-0',
            config.opacity,
            'motion-reduce:opacity-30'
          )}
        >
          {/* Primary aurora wave - cyan/blue */}
          <div
            className={cn(
              'absolute -top-[40%] -left-[20%] w-[140%] h-[80%]',
              'bg-gradient-to-r from-cyan-400/80 via-blue-400/70 to-indigo-400/80',
              'dark:from-cyan-400/90 dark:via-blue-400/80 dark:to-indigo-400/90',
              config.blur,
              'animate-aurora-1'
            )}
            style={{
              borderRadius: '40%',
              transform: 'rotate(-12deg)',
            }}
          />

          {/* Secondary aurora wave - purple/pink */}
          <div
            className={cn(
              'absolute -top-[30%] left-[10%] w-[120%] h-[70%]',
              'bg-gradient-to-r from-violet-400/80 via-purple-400/70 to-fuchsia-400/80',
              'dark:from-violet-400/90 dark:via-purple-400/80 dark:to-fuchsia-400/90',
              config.blur,
              'animate-aurora-2'
            )}
            style={{
              borderRadius: '45%',
              transform: 'rotate(8deg)',
            }}
          />

          {/* Tertiary aurora wave - teal/emerald */}
          <div
            className={cn(
              'absolute top-[20%] -right-[10%] w-[100%] h-[60%]',
              'bg-gradient-to-l from-teal-400/80 via-emerald-400/70 to-cyan-400/80',
              'dark:from-teal-400/90 dark:via-emerald-400/80 dark:to-cyan-400/90',
              config.blur,
              'animate-aurora-3'
            )}
            style={{
              borderRadius: '50%',
              transform: 'rotate(-5deg)',
            }}
          />

          {/* Bottom glow accent */}
          <div
            className={cn(
              'absolute -bottom-[20%] left-[20%] w-[60%] h-[50%]',
              'bg-gradient-to-t from-blue-500/60 via-indigo-400/50 to-transparent',
              'dark:from-blue-400/70 dark:via-indigo-400/60 dark:to-transparent',
              'blur-xl',
              'animate-aurora-glow'
            )}
            style={{
              borderRadius: '50%',
            }}
          />
        </div>

        {/* Subtle noise overlay for texture */}
        <div className="absolute inset-0 opacity-[0.02] dark:opacity-[0.04] bg-noise-texture" />

        {/* Vignette effect */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,var(--background)_95%)]" />
      </div>
    )
  }

  // Mesh variant - animated gradient mesh
  if (variant === 'mesh') {
    return (
      <div
        className={cn(
          'fixed inset-0 z-0 overflow-hidden pointer-events-none',
          className
        )}
        aria-hidden="true"
      >
        <div className="absolute inset-0 bg-background" />

        <div className={cn('absolute inset-0', config.opacity)}>
          {/* Mesh gradient blobs */}
          <div
            className={cn(
              'absolute top-0 left-0 w-[50%] h-[50%]',
              'bg-gradient-to-br from-violet-500/40 to-transparent',
              'dark:from-violet-400/50',
              'blur-3xl animate-mesh-1'
            )}
          />
          <div
            className={cn(
              'absolute top-0 right-0 w-[50%] h-[50%]',
              'bg-gradient-to-bl from-cyan-500/40 to-transparent',
              'dark:from-cyan-400/50',
              'blur-3xl animate-mesh-2'
            )}
          />
          <div
            className={cn(
              'absolute bottom-0 left-0 w-[50%] h-[50%]',
              'bg-gradient-to-tr from-emerald-500/30 to-transparent',
              'dark:from-emerald-400/40',
              'blur-3xl animate-mesh-3'
            )}
          />
          <div
            className={cn(
              'absolute bottom-0 right-0 w-[50%] h-[50%]',
              'bg-gradient-to-tl from-rose-500/30 to-transparent',
              'dark:from-rose-400/40',
              'blur-3xl animate-mesh-4'
            )}
          />
          {/* Center glow */}
          <div
            className={cn(
              'absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2',
              'w-[40%] h-[40%]',
              'bg-gradient-to-r from-blue-500/20 via-purple-500/20 to-pink-500/20',
              'dark:from-blue-400/30 dark:via-purple-400/30 dark:to-pink-400/30',
              'blur-3xl animate-mesh-center'
            )}
          />
        </div>

        <div className="absolute inset-0 opacity-[0.015] dark:opacity-[0.03] bg-noise-texture" />
      </div>
    )
  }

  // Beams variant - glowing light beams
  if (variant === 'beams') {
    return (
      <div
        className={cn(
          'fixed inset-0 z-0 overflow-hidden pointer-events-none',
          className
        )}
        aria-hidden="true"
      >
        <div className="absolute inset-0 bg-background" />

        <div className={cn('absolute inset-0', config.opacity)}>
          {/* Diagonal beam 1 */}
          <div
            className={cn(
              'absolute -top-[50%] left-[10%] w-[200px] h-[200%]',
              'bg-gradient-to-b from-transparent via-cyan-500/30 to-transparent',
              'dark:via-cyan-400/40',
              'blur-2xl animate-beam-1'
            )}
            style={{ transform: 'rotate(35deg)' }}
          />
          {/* Diagonal beam 2 */}
          <div
            className={cn(
              'absolute -top-[50%] left-[40%] w-[150px] h-[200%]',
              'bg-gradient-to-b from-transparent via-violet-500/25 to-transparent',
              'dark:via-violet-400/35',
              'blur-2xl animate-beam-2'
            )}
            style={{ transform: 'rotate(40deg)' }}
          />
          {/* Diagonal beam 3 */}
          <div
            className={cn(
              'absolute -top-[50%] right-[20%] w-[180px] h-[200%]',
              'bg-gradient-to-b from-transparent via-blue-500/25 to-transparent',
              'dark:via-blue-400/35',
              'blur-2xl animate-beam-3'
            )}
            style={{ transform: 'rotate(30deg)' }}
          />
          {/* Horizontal glow */}
          <div
            className={cn(
              'absolute top-[30%] left-0 right-0 h-[300px]',
              'bg-gradient-to-r from-transparent via-indigo-500/15 to-transparent',
              'dark:via-indigo-400/25',
              'blur-3xl animate-beam-glow'
            )}
          />
        </div>

        <div className="absolute inset-0 opacity-[0.02] dark:opacity-[0.04] bg-noise-texture" />
      </div>
    )
  }

  // Particles variant - floating dots
  return (
    <div
      className={cn(
        'fixed inset-0 z-0 overflow-hidden pointer-events-none',
        className
      )}
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-background" />

      <div className={cn('absolute inset-0', config.opacity)}>
        {/* Particle dots - using CSS only */}
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className={cn(
              'absolute rounded-full',
              'bg-gradient-to-br from-cyan-400 to-blue-500',
              'dark:from-cyan-300 dark:to-blue-400',
              i % 3 === 0 ? 'w-2 h-2' : i % 3 === 1 ? 'w-1.5 h-1.5' : 'w-1 h-1',
              'animate-particle'
            )}
            style={{
              left: `${(i * 5) % 100}%`,
              top: `${(i * 7) % 100}%`,
              animationDelay: `${i * 0.3}s`,
              animationDuration: `${15 + (i % 5) * 3}s`,
            }}
          />
        ))}

        {/* Gradient overlay */}
        <div
          className={cn(
            'absolute inset-0',
            'bg-gradient-to-br from-cyan-500/5 via-transparent to-violet-500/5',
            'dark:from-cyan-400/10 dark:to-violet-400/10'
          )}
        />
      </div>

      <div className="absolute inset-0 opacity-[0.015] dark:opacity-[0.03] bg-noise-texture" />
    </div>
  )
}

export default AnimatedBackground
