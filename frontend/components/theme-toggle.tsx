'use client'

import * as React from 'react'
import { useTheme } from 'next-themes'
import { Moon, Sun, Monitor } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

/**
 * Simple theme toggle button that switches between light and dark modes
 * with smooth icon transition animation
 */
export function ThemeToggle() {
  const { setTheme, resolvedTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  const toggleTheme = () => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')
  }

  if (!mounted) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className={cn(
          'relative overflow-hidden',
          'bg-white/10 backdrop-blur-md border border-white/20',
          'dark:bg-black/20 dark:border-white/10',
          'hover:bg-white/20 dark:hover:bg-white/10',
          'transition-all duration-300'
        )}
        disabled
      >
        <div className="size-5 animate-pulse rounded-full bg-muted" />
        <span className="sr-only">Loading theme toggle</span>
      </Button>
    )
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      className={cn(
        'relative overflow-hidden group',
        'bg-white/10 backdrop-blur-md border border-white/20',
        'dark:bg-black/20 dark:border-white/10',
        'hover:bg-white/20 dark:hover:bg-white/10',
        'hover:border-white/30 dark:hover:border-white/20',
        'transition-all duration-300 ease-out',
        'hover:scale-105 active:scale-95'
      )}
      aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`}
    >
      <Sun
        className={cn(
          'absolute size-5 transition-all duration-500 ease-out',
          'text-amber-400',
          resolvedTheme === 'dark'
            ? 'rotate-0 scale-100 opacity-100'
            : 'rotate-90 scale-0 opacity-0'
        )}
      />
      <Moon
        className={cn(
          'absolute size-5 transition-all duration-500 ease-out',
          'text-slate-700 dark:text-slate-400',
          resolvedTheme === 'dark'
            ? '-rotate-90 scale-0 opacity-0'
            : 'rotate-0 scale-100 opacity-100'
        )}
      />
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}

export function ThemeToggleDropdown() {
  const { theme, setTheme, resolvedTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className={cn(
          'relative overflow-hidden',
          'bg-white/10 backdrop-blur-md border border-white/20',
          'dark:bg-black/20 dark:border-white/10',
          'hover:bg-white/20 dark:hover:bg-white/10',
          'transition-all duration-300'
        )}
        disabled
      >
        <div className="size-5 animate-pulse rounded-full bg-muted" />
        <span className="sr-only">Loading theme toggle</span>
      </Button>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'relative overflow-hidden group',
            'bg-white/10 backdrop-blur-md border border-white/20',
            'dark:bg-black/20 dark:border-white/10',
            'hover:bg-white/20 dark:hover:bg-white/10',
            'hover:border-white/30 dark:hover:border-white/20',
            'transition-all duration-300 ease-out',
            'hover:scale-105 active:scale-95',
            'data-[state=open]:bg-white/20 dark:data-[state=open]:bg-white/10'
          )}
          aria-label="Select theme"
        >
          <Sun
            className={cn(
              'absolute size-5 transition-all duration-500 ease-out',
              'text-amber-400',
              resolvedTheme === 'dark'
                ? 'rotate-0 scale-100 opacity-100'
                : 'rotate-90 scale-0 opacity-0'
            )}
          />
          <Moon
            className={cn(
              'absolute size-5 transition-all duration-500 ease-out',
              'text-slate-700 dark:text-slate-400',
              resolvedTheme === 'dark'
                ? '-rotate-90 scale-0 opacity-0'
                : 'rotate-0 scale-100 opacity-100'
            )}
          />
          <span className="sr-only">Select theme</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className={cn(
          'min-w-[140px]',
          'bg-white/80 dark:bg-black/80',
          'backdrop-blur-xl',
          'border border-white/20 dark:border-white/10',
          'shadow-xl shadow-black/5 dark:shadow-black/20'
        )}
      >
        <DropdownMenuItem
          onClick={() => setTheme('light')}
          className={cn(
            'flex items-center gap-2 cursor-pointer',
            'transition-colors duration-200',
            theme === 'light' && 'bg-accent'
          )}
        >
          <Sun className="size-4 text-amber-500" />
          <span>Light</span>
          {theme === 'light' && (
            <span className="ml-auto text-xs text-muted-foreground">Active</span>
          )}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme('dark')}
          className={cn(
            'flex items-center gap-2 cursor-pointer',
            'transition-colors duration-200',
            theme === 'dark' && 'bg-accent'
          )}
        >
          <Moon className="size-4 text-slate-500 dark:text-slate-400" />
          <span>Dark</span>
          {theme === 'dark' && (
            <span className="ml-auto text-xs text-muted-foreground">Active</span>
          )}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme('system')}
          className={cn(
            'flex items-center gap-2 cursor-pointer',
            'transition-colors duration-200',
            theme === 'system' && 'bg-accent'
          )}
        >
          <Monitor className="size-4 text-blue-500 dark:text-blue-400" />
          <span>System</span>
          {theme === 'system' && (
            <span className="ml-auto text-xs text-muted-foreground">Active</span>
          )}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
