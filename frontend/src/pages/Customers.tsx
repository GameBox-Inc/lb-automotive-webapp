import React, { useState, useEffect } from 'react'
import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from '@headlessui/react'
import { Search, Phone, Mail, MapPin, Plus, X } from 'lucide-react'
import { supabase } from '../lib/supabase'
import toast from 'react-hot-toast'

interface Customer {
  id: string
  name: string
  phone: string
  email: string
  address: string
  created_at: string
  last_visit: string
}

export function Customers() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [newCustomer, setNewCustomer] = useState({
    name: '',
    phone: '',
    email: '',
    address: ''
  })

  useEffect(() => {
    fetchCustomers()
  }, [])

  async function fetchCustomers() {
    try {
      const { data, error } = await supabase
        .from('customers')
        .select('*')
        .order('name')

      if (error) throw error
      setCustomers(data || [])
    } catch (error) {
      console.error('Error fetching customers:', error)
      toast.error('Failed to load customers')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    try {
      const { data, error } = await supabase
        .from('customers')
        .select('*')
        .or(`name.ilike.%${searchTerm}%,phone.ilike.%${searchTerm}%,email.ilike.%${searchTerm}%`)
        .order('name')

      if (error) throw error
      setCustomers(data || [])
    } catch (error) {
      console.error('Error searching customers:', error)
      toast.error('Failed to search customers')
    }
  }

  const handleAddCustomer = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const { error } = await supabase
        .from('customers')
        .insert([newCustomer])

      if (error) throw error

      toast.success('Customer added successfully')
      setShowAddModal(false)
      setNewCustomer({
        name: '',
        phone: '',
        email: '',
        address: ''
      })
      fetchCustomers()
    } catch (error) {
      console.error('Error adding customer:', error)
      toast.error('Failed to add customer')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Customers</h1>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-lb-red-primary hover:bg-lb-red-light"
        >
          <Plus className="h-5 w-5 mr-2" />
          Add Customer
        </button>
      </div>

      <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
        <div className="flex gap-4 mb-6">
          <div className="flex-1">
            <div className="relative">
              <input
                type="text"
                placeholder="Search by name, phone, or email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-lb-red-primary focus:border-lb-red-primary text-gray-900 dark:text-white placeholder:text-gray-500 dark:placeholder:text-gray-400 bg-white dark:bg-gray-900/40"
              />
              <Search className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
            </div>
          </div>
          <button
            onClick={handleSearch}
            className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            Search
          </button>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-500 dark:text-gray-300">Loading customers...</p>
          </div>
        ) : customers.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 dark:text-gray-300">No customers found</p>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {customers.map((customer) => (
              <div
                key={customer.id}
                className="bg-gray-50 dark:bg-gray-900/40 rounded-lg p-4 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors"
              >
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">{customer.name}</h3>
                <div className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
                  <div className="flex items-center gap-2">
                    <Phone className="h-4 w-4" />
                    <span>{customer.phone}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Mail className="h-4 w-4" />
                    <span>{customer.email}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4" />
                    <span>{customer.address}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Transition show={showAddModal}>
        <Dialog open={showAddModal} onClose={() => setShowAddModal(false)} className="relative z-50">
          <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-150" leaveFrom="opacity-100" leaveTo="opacity-0">
            <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
          </TransitionChild>
          <div className="fixed inset-0 flex items-center justify-center p-4">
            <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0 scale-95" enterTo="opacity-100 scale-100" leave="ease-in duration-150" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-95">
              <DialogPanel className="bg-white dark:bg-gray-800 p-6 rounded-lg w-full max-w-md shadow-xl">
                <div className="flex justify-between items-center mb-4">
                  <DialogTitle className="text-lg font-medium text-gray-900 dark:text-white">Add New Customer</DialogTitle>
                  <button type="button" onClick={() => setShowAddModal(false)} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">
                    <X className="h-5 w-5 text-gray-500" />
                  </button>
                </div>
                <form onSubmit={handleAddCustomer} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Name</label>
                    <input
                      type="text"
                      value={newCustomer.name}
                      onChange={(e) => setNewCustomer({ ...newCustomer, name: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary text-gray-900 dark:text-white bg-white dark:bg-gray-900/40 placeholder:text-gray-500 dark:placeholder:text-gray-400"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Phone</label>
                    <input
                      type="tel"
                      value={newCustomer.phone}
                      onChange={(e) => setNewCustomer({ ...newCustomer, phone: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary text-gray-900 dark:text-white bg-white dark:bg-gray-900/40 placeholder:text-gray-500 dark:placeholder:text-gray-400"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Email</label>
                    <input
                      type="email"
                      value={newCustomer.email}
                      onChange={(e) => setNewCustomer({ ...newCustomer, email: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary text-gray-900 dark:text-white bg-white dark:bg-gray-900/40 placeholder:text-gray-500 dark:placeholder:text-gray-400"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Address</label>
                    <textarea
                      value={newCustomer.address}
                      onChange={(e) => setNewCustomer({ ...newCustomer, address: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary text-gray-900 dark:text-white bg-white dark:bg-gray-900/40 placeholder:text-gray-500 dark:placeholder:text-gray-400"
                      rows={3}
                      required
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setShowAddModal(false)}
                      className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-2 text-sm font-medium text-white bg-lb-red-primary rounded-md hover:bg-lb-red-light"
                    >
                      Add Customer
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </Dialog>
      </Transition>
    </div>
  )
}