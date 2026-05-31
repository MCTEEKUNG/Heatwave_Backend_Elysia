import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import TabBar, { type TabKey } from './TabBar'

describe('TabBar', () => {
  it('renders all tabs and marks the active one', () => {
    render(<TabBar active="train" onSelect={() => {}} />)
    expect(screen.getByRole('tab', { name: /Train/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /Lab/ })).toHaveAttribute('aria-selected', 'false')
    for (const t of ['Pipeline', 'Train', 'Forecast', 'Ops', 'Lab'])
      expect(screen.getByRole('tab', { name: new RegExp(t) })).toBeInTheDocument()
  })

  it('calls onSelect with the tab key when clicked', () => {
    const onSelect = vi.fn()
    render(<TabBar active="train" onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('tab', { name: /Lab/ }))
    expect(onSelect).toHaveBeenCalledWith('lab' satisfies TabKey)
  })
})
