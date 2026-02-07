import type { Metadata } from 'next'
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import { Analytics } from '@vercel/analytics/next'
import { ThemeProvider } from '@/components/theme-provider'
import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'Madrox Monitor',
    template: '%s | Madrox Monitor',
  },
  description: 'Real-time multi-agent orchestration and monitoring platform for Claude instances',
  keywords: ['madrox', 'multi-agent', 'orchestration', 'monitoring', 'claude', 'ai', 'real-time'],
  authors: [{ name: 'Madrox Team' }],
  creator: 'Madrox',
  publisher: 'Madrox',
  metadataBase: new URL('http://localhost:3000'),
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: '/',
    title: 'Madrox Monitor',
    description: 'Real-time multi-agent orchestration and monitoring platform for Claude instances',
    siteName: 'Madrox Monitor',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Madrox Monitor',
    description: 'Real-time multi-agent orchestration and monitoring platform for Claude instances',
    creator: '@madrox',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  icons: {
    icon: '/favicon.ico',
    shortcut: '/favicon-16x16.png',
    apple: '/apple-touch-icon.png',
  },
  manifest: '/site.webmanifest',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`font-sans ${GeistSans.variable} ${GeistMono.variable}`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={true}
          disableTransitionOnChange={false}
        >
          {children}
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
