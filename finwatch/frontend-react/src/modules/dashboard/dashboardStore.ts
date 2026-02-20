import { create } from 'zustand'

type DashboardState = {
  timeWindowHours: number
  setTimeWindowHours: (hours: number) => void
  isRunningPipeline: boolean
  setIsRunningPipeline: (value: boolean) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  timeWindowHours: 24,
  setTimeWindowHours: (hours) => set({ timeWindowHours: hours }),
  isRunningPipeline: false,
  setIsRunningPipeline: (value) => set({ isRunningPipeline: value }),
}))
