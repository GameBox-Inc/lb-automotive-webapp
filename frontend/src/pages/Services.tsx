import React, { useState, useEffect } from 'react'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { Search, Plus, Edit2, Trash2, X, AlertTriangle, Filter, Clock, DollarSign, AlertCircle, Pencil, Tag, Save } from 'lucide-react'
import { formatCurrency } from '../utils/format'
import { apiClient, Service } from '../lib/supabase'
import toast from 'react-hot-toast'

export function Services() {
  const [services, setServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)
  const [isAdmin, setIsAdmin] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [isEditing, setIsEditing] = useState(false)

  // Form State
  const [currentService, setCurrentService] = useState<Partial<Service>>({
    name: '',
    description: '',
    duration: 30,
    price: 0,
    is_emergency: false,
    category: 'maintenance'
  })

  useEffect(() => {
    checkAdmin()
    fetchServices()
  }, [])

  const checkAdmin = () => {
    const user = apiClient.getStoredUser()
    setIsAdmin(!!user?.is_admin)
  }

  const fetchServices = async () => {
    try {
      const data = await apiClient.getServices()
      setServices(data)
      setLoading(false)
    } catch (error) {
      console.error('Error fetching services:', error)
      toast.error('Failed to load services')
      setLoading(false)
    }
  }

  const handleOpenAdd = () => {
    setIsEditing(false)
    setCurrentService({
      name: '',
      description: '',
      duration: 30,
      price: 0,
      is_emergency: false,
      category: 'maintenance'
    })
    setShowModal(true)
  }

  const handleOpenEdit = (service: Service) => {
    setIsEditing(true)
    setCurrentService({ ...service })
    setShowModal(true)
  }

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete "${name}"?`)) return

    try {
      await apiClient.deleteService(id)
      toast.success('Service deleted successfully')
      fetchServices()
    } catch (error) {
      console.error('Error deleting service:', error)
      toast.error('Failed to delete service')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      // Validate common fields
      if (!currentService.name || !currentService.description || currentService.price === undefined) {
        toast.error('Please fill in all required fields')
        return
      }

      if (isEditing && currentService.id) {
        await apiClient.updateService(currentService.id, currentService)
        toast.success('Service updated successfully')
      } else {
        await apiClient.createService(currentService as Omit<Service, 'id'>)
        toast.success('Service created successfully')
      }

      setShowModal(false)
      fetchServices()
    } catch (error) {
      console.error('Error saving service:', error)
      toast.error('Failed to save service')
    }
  }

  // Pre-defined categories; merge with any from API so nothing is hidden
  const base = ['maintenance', 'repair', 'diagnostic', 'emergency', 'inspection', 'other', 'general']
  const fromApi = [...new Set(services.map(s => (s as any).category ?? 'general').filter(Boolean))]
  const categories = [...new Set([...base, ...fromApi])]

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 p-6">
        <LoadingSpinner size="lg" className="mx-auto" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Services Catalog</h1>
          <p className="text-gray-500 text-sm mt-1">
            {isAdmin ? 'Manage and view available services' : 'View available services'}
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={handleOpenAdd}
            className="px-4 py-2 bg-red-700 text-white rounded-lg hover:bg-red-800 shadow-sm transition-colors flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Add New Service
          </button>
        )}
      </div>

      {categories.map(category => {
        const categoryServices = services.filter(service => (service?.category ?? 'general') === category);
        if (categoryServices.length === 0) return null;

        return (
          <div key={category} className="mb-8">
            <h2 className="text-xl font-semibold text-gray-800 mb-4 capitalize flex items-center gap-2">
              <span className="w-2 h-8 bg-red-600 rounded-full inline-block"></span>
              {category} Services
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {categoryServices.map(service => (
                <div
                  key={service.id}
                  className="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-all duration-200 border border-gray-100 relative group"
                >
                  <div className="flex items-start justify-between mb-4">
                    <h3 className="text-lg font-bold text-gray-900 pr-8">{service.name}</h3>
                    {service.is_emergency && (
                      <span className="px-2 py-1 bg-red-100 text-red-800 text-xs font-bold rounded-full flex items-center gap-1 absolute top-6 right-6">
                        <AlertCircle className="h-3 w-3" />
                        Emergency
                      </span>
                    )}
                  </div>
                  <p className="text-gray-600 mb-6 text-sm leading-relaxed min-h-[40px]">{service.description}</p>

                  <div className="flex items-center justify-between pt-4 border-t border-gray-50">
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <div className="flex items-center gap-1.5 bg-gray-50 px-2 py-1 rounded">
                        <Clock className="h-4 w-4 text-gray-400" />
                        <span className="font-medium">{service.duration}m</span>
                      </div>
                      <div className="flex items-center gap-1.5 bg-gray-50 px-2 py-1 rounded">
                        <DollarSign className="h-4 w-4 text-green-600" />
                        <span className="font-bold text-gray-900 dark:text-white">{formatCurrency(service.price)}</span>
                      </div>
                    </div>

                    {isAdmin && (
                      <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => handleOpenEdit(service)}
                          className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-full transition-colors"
                          title="Edit Service"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(service.id, service.name)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-full transition-colors"
                          title="Delete Service"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      })}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center p-6 border-b sticky top-0 bg-white z-10">
              <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                {isEditing ? <Pencil className="h-5 w-5 text-indigo-600" /> : <Plus className="h-5 w-5 text-red-600" />}
                {isEditing ? 'Edit Service' : 'Add New Service'}
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-6">

              {/* Basic Info Section */}
              <div className="space-y-6">
                <h4 className="text-sm font-semibold text-gray-900 uppercase tracking-wider border-b pb-2">Service Details</h4>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">Service Name</label>
                    <input
                      type="text"
                      value={currentService.name}
                      onChange={e => setCurrentService({ ...currentService, name: e.target.value })}
                      className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-red-500 focus:border-red-500 transition-all"
                      required
                      placeholder="e.g. Synthetic Oil Change"
                    />
                  </div>

                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
                    <textarea
                      value={currentService.description}
                      onChange={e => setCurrentService({ ...currentService, description: e.target.value })}
                      className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-red-500 focus:border-red-500 transition-all"
                      required
                      rows={3}
                      placeholder="Describe what this service entails..."
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      <div className="flex items-center gap-2">
                        <Tag className="h-4 w-4" />
                        Category
                      </div>
                    </label>
                    <select
                      value={currentService.category}
                      onChange={e => setCurrentService({ ...currentService, category: e.target.value })}
                      className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-red-500 focus:border-red-500 transition-all capitalize"
                    >
                      {categories.map(cat => (
                        <option key={cat} value={cat} className="capitalize">{cat}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="flex items-center gap-2 cursor-pointer mt-8 p-2 rounded-lg hover:bg-gray-50 transition-colors border border-transparent hover:border-gray-200">
                      <input
                        type="checkbox"
                        checked={currentService.is_emergency}
                        onChange={e => setCurrentService({ ...currentService, is_emergency: e.target.checked })}
                        className="h-5 w-5 text-red-600 focus:ring-red-500 border-gray-300 rounded"
                      />
                      <span className="text-sm font-medium text-gray-900 flex items-center gap-2">
                        <AlertCircle className="h-4 w-4 text-red-600" />
                        Mark as Emergency Service
                      </span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Pricing & Duration Section */}
              <div className="space-y-6">
                <h4 className="text-sm font-semibold text-gray-900 uppercase tracking-wider border-b pb-2">Pricing & Configuration</h4>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4" />
                        Duration (minutes)
                      </div>
                    </label>
                    <input
                      type="number"
                      value={currentService.duration}
                      onChange={e => setCurrentService({ ...currentService, duration: parseInt(e.target.value) })}
                      className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-red-500 focus:border-red-500 transition-all font-mono"
                      required
                      min="5"
                      step="5"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      <div className="flex items-center gap-2">
                        <DollarSign className="h-4 w-4" />
                        Price ($)
                      </div>
                    </label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                      <input
                        type="number"
                        value={currentService.price}
                        onChange={e => setCurrentService({ ...currentService, price: parseFloat(e.target.value) })}
                        className="w-full pl-8 pr-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-red-500 focus:border-red-500 transition-all font-mono"
                        required
                        min="0"
                        step="0.01"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-6 border-t mt-6">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors border border-gray-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-6 py-2.5 text-sm font-medium text-white bg-red-700 hover:bg-red-800 rounded-lg shadow-md hover:shadow-lg transition-all flex items-center gap-2"
                >
                  {isEditing ? (
                    <>
                      <Save className="h-4 w-4" />
                      Save Changes
                    </>
                  ) : (
                    <>
                      <Plus className="h-4 w-4" />
                      Create Service
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
export default Services
