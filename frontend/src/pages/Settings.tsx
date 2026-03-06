import React, { useState, useEffect } from 'react'
import { apiClient } from '../lib/supabase'
import { Setting } from '../types'
import toast from 'react-hot-toast'
import { LoadingSpinner } from '../components/LoadingSpinner'

export function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Common timezones
  const timezones = [
    'UTC',
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'Europe/London',
    'Europe/Paris',
    'Asia/Tokyo',
    'Australia/Sydney'
  ]

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const data = await apiClient.getSettings()
      // Convert array to object for easier access
      const settingsMap = data.reduce((acc: Record<string, string>, curr: Setting) => {
        acc[curr.key] = curr.value
        return acc
      }, {})
      setSettings(settingsMap)
    } catch (error) {
      console.error('Error fetching settings:', error)
      toast.error('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (key: string, value: string) => {
    setSaving(true)
    try {
      await apiClient.updateSetting(key, value)
      setSettings(prev => ({ ...prev, [key]: value }))
      toast.success('Setting updated')
    } catch (error) {
      console.error('Error updating setting:', error)
      toast.error('Failed to update setting')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Settings</h1>
      </div>

      <div className="bg-white dark:bg-gray-800 shadow rounded-lg">
        <div className="p-6 space-y-6">
          <div className="border-b border-gray-200 dark:border-gray-700 pb-6">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white">General Settings</h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Configure global application settings.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6">

            {/* Timezone Setting */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Business Timezone
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                All appointments and schedules will be displayed in this timezone.
              </p>
              <select
                value={settings['timezone'] || 'America/New_York'}
                onChange={(e) => handleSave('timezone', e.target.value)}
                disabled={saving}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white sm:text-sm"
              >
                {timezones.map(tz => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>

            {/* Staff Count Setting */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Daily Staff Count
              </label>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                Maximum number of active staff visible on the schedule.
              </p>
              <input
                type="number"
                value={settings['staff_count'] || '5'}
                onChange={(e) => handleSave('staff_count', e.target.value)}
                disabled={saving}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white sm:text-sm"
              />
            </div>

            {/* Business Email */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Business Email
              </label>
              <input
                type="email"
                defaultValue="contact@lbautomotive.com"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white sm:text-sm"
                disabled
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Contact admin to change.</p>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings;
