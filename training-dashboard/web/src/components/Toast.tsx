import { useEffect, useRef, useState } from 'react'

export type ToastKind = 'success' | 'error'

export interface ToastMessage {
  kind: ToastKind
  text: string
  /** Bumped each time so repeated identical messages still re-trigger. */
  nonce: number
}

function fireNotification(title: string, body: string) {
  if (typeof window === 'undefined' || !('Notification' in window)) return
  try {
    if (Notification.permission === 'granted') {
      new Notification(title, { body })
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission()
        .then((perm) => {
          if (perm === 'granted') new Notification(title, { body })
        })
        .catch(() => {
          /* ignore */
        })
    }
  } catch {
    /* Notification unavailable / blocked — ignore */
  }
}

export default function Toast({ message }: { message: ToastMessage | null }) {
  const [visible, setVisible] = useState(false)
  const [current, setCurrent] = useState<ToastMessage | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!message) return
    setCurrent(message)
    setVisible(true)
    fireNotification(
      message.kind === 'success' ? 'Training complete' : 'Training error',
      message.text,
    )
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setVisible(false), 5000)
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [message])

  if (!current) return null

  return (
    <div
      className={`toast toast-${current.kind} ${visible ? 'toast-show' : 'toast-hide'}`}
      role="status"
      aria-live="polite"
    >
      {current.text}
    </div>
  )
}
