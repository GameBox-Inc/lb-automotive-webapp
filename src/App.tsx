import React, { useEffect, useState } from 'react'
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom'
import { Calendar, Clock, Phone, Settings, PenTool as Tool, User, Menu, Home, FileText, BarChart3, X, LogOut, Users } from 'lucide-react'
import { Toaster } from 'react-hot-toast'
import { supabase } from './lib/supabase'
import { AppointmentCard } from './components/AppointmentCard'
import { Dashboard } from './pages/Dashboard'
import { Appointments } from './pages/Appointments'
import { Services } from './pages/Services'
import { Reports } from './pages/Reports'
import { Analytics } from './pages/Analytics'
import { Settings as SettingsPage } from './pages/Settings'
import { Customers } from './pages/Customers'
import { Login } from './pages/Login'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [session, setSession] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (!session && location.pathname !== '/login') {
        navigate('/login')
      }
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (!session && location.pathname !== '/login') {
        navigate('/login')
      } else if (session && location.pathname === '/login') {
        navigate('/')
      }
    })

    return () => subscription.unsubscribe()
  }, [navigate, location])

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  const NavItem = ({ icon, text, to, active = false }) => {
    const location = useLocation()
    const isActive = location.pathname === to

    return (
      <Link
        to={to}
        className={`flex items-center gap-3 px-6 py-3 text-sm font-medium ${
          isActive
            ? 'bg-blue-600 text-white'
            : 'text-gray-300 hover:bg-gray-800 hover:text-white'
        }`}
      >
        {icon}
        <span>{text}</span>
      </Link>
    )
  }

  const Sidebar = () => (
    <div
      className={`fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 text-white transform transition-transform duration-200 ease-in-out ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      } lg:translate-x-0`}
    >
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <h1 className="text-xl font-bold">LB Automotive</h1>
        <button
          className="lg:hidden text-white"
          onClick={() => setSidebarOpen(false)}
        >
          <X className="h-6 w-6" />
        </button>
      </div>
      <nav className="mt-8 flex flex-col h-[calc(100%-5rem)]">
        <div className="flex-1">
          <NavItem icon={<Home className="h-5 w-5" />} text="Dashboard" to="/" />
          <NavItem icon={<Calendar className="h-5 w-5" />} text="Appointments" to="/appointments" />
          <NavItem icon={<Users className="h-5 w-5" />} text="Customers" to="/customers" />
          <NavItem icon={<Tool className="h-5 w-5" />} text="Services" to="/services" />
          <NavItem icon={<FileText className="h-5 w-5" />} text="Reports" to="/reports" />
          <NavItem icon={<BarChart3 className="h-5 w-5" />} text="Analytics" to="/analytics" />
          <NavItem icon={<Settings className="h-5 w-5" />} text="Settings" to="/settings" />
        </div>
        <button
          onClick={handleSignOut}
          className="flex items-center gap-3 px-6 py-3 text-sm font-medium text-red-400 hover:bg-gray-800 hover:text-red-300 mb-4"
        >
          <LogOut className="h-5 w-5" />
          <span>Sign Out</span>
        </button>
      </nav>
    </div>
  )

  if (location.pathname === '/login') {
    return <Login />
  }

  if (!session) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Toaster position="top-right" />
      <Sidebar />

      <div className="lg:pl-64">
        <header className="bg-white shadow-sm">
          <div className="flex items-center justify-between px-4 py-4">
            <button
              className="lg:hidden text-gray-600"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-6 w-6" />
            </button>
            <div className="flex items-center gap-4">
              <div className="relative">
                <img
                  src="https://images.pexels.com/photos/2244746/pexels-photo-2244746.jpeg"
                  alt="Profile"
                  className="w-8 h-8 rounded-full"
                />
              </div>
            </div>
          </div>
        </header>

        <main className="p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/appointments" element={<Appointments />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/services" element={<Services />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default App