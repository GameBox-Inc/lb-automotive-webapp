import React from 'react'
import { BarChart3, TrendingUp, Users, DollarSign } from 'lucide-react'

export function Analytics() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">Analytics Dashboard</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">Total Revenue</h3>
            <DollarSign className="h-6 w-6 text-green-500" />
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">$24,563</p>
          <p className="text-sm text-gray-500 dark:text-gray-300 mt-2">+12.5% from last month</p>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">Customer Growth</h3>
            <Users className="h-6 w-6 text-blue-500" />
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">1,203</p>
          <p className="text-sm text-gray-500 dark:text-gray-300 mt-2">+8.2% new customers</p>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">Service Efficiency</h3>
            <TrendingUp className="h-6 w-6 text-purple-500" />
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">94%</p>
          <p className="text-sm text-gray-500 dark:text-gray-300 mt-2">Average completion rate</p>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">Emergency Response</h3>
            <BarChart3 className="h-6 w-6 text-red-500" />
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">15min</p>
          <p className="text-sm text-gray-500 dark:text-gray-300 mt-2">Average response time</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="text-lg font-medium mb-4 text-gray-900 dark:text-white">Monthly Service Trends</h3>
          <div className="h-64 flex items-center justify-center">
            <p className="text-gray-500 dark:text-gray-300">Chart will be implemented here</p>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="text-lg font-medium mb-4 text-gray-900 dark:text-white">Customer Satisfaction</h3>
          <div className="h-64 flex items-center justify-center">
            <p className="text-gray-500 dark:text-gray-300">Chart will be implemented here</p>
          </div>
        </div>
      </div>
    </div>
  )
}