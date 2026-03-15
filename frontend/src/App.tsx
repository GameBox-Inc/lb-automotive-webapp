import { useState, useEffect, Suspense, lazy, startTransition } from 'react'
import { Routes, Route, Link, useLocation, Navigate, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Calendar, Settings, LogOut, Wrench, PenTool as Tool, Phone, Users } from 'lucide-react'
import { Toaster } from 'react-hot-toast'
import { useAppDispatch, useAppSelector } from './store/hooks'
import { checkAuth, logoutUser, setLoading } from './store/slices/authSlice'
import { ErrorBoundary } from './components/ErrorBoundary'

// Lazy load pages for performance
const Dashboard = lazy(() => import('./pages/Dashboard').then(module => ({ default: module.Dashboard })))
const Appointments = lazy(() => import('./pages/Appointments').then(module => ({ default: module.Appointments })))
const Services = lazy(() => import('./pages/Services').then(module => ({ default: module.Services })))
const SettingsPage = lazy(() => import('./pages/Settings').then(module => ({ default: module.Settings })))
const Login = lazy(() => import('./pages/Login').then(module => ({ default: module.Login })))
const AdminIVR = lazy(() => import('./pages/AdminIVR'))
const AdminCustomers = lazy(() => import('./pages/AdminCustomers'))
const AdminStaff = lazy(() => import('./pages/AdminStaff'))
const StaffDashboard = lazy(() => import('./pages/StaffDashboard'))
const CaseDetails = lazy(() => import('./pages/CaseDetails'))
const CheckIn = lazy(() => import('./pages/CheckIn'))

// Loading component
const PageLoader = () => (
  <div className="flex items-center justify-center h-full min-h-[400px]">
    <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-lb-red-primary"></div>
  </div>
)

function App() {
  const dispatch = useAppDispatch()
  const { user, loading, isAuthenticated } = useAppSelector((state) => state.auth)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    // Check if user is authenticated via Redux
    // Only skip auth check if we're on the login page AND have no token to verify
    if (location.pathname !== '/login' || !!localStorage.getItem('auth_token')) {
      dispatch(checkAuth())
    } else {
      // If we are on /login and have no token, stop loading to show the login form
      dispatch(setLoading(false))
    }
  }, [dispatch, location.pathname])

  useEffect(() => {
    // Handle redirects based on auth state
    if (!loading) {
      startTransition(() => {
        if (isAuthenticated && location.pathname === '/login') {
          navigate('/', { replace: true })
        } else if (!isAuthenticated && location.pathname !== '/login') {
          navigate('/login', { replace: true })
        }
      })
    }

    const handleUnauthorized = () => {
      dispatch(logoutUser())
      startTransition(() => {
        navigate('/login', { replace: true })
      })
    }

    window.addEventListener('auth:unauthorized', handleUnauthorized)

    return () => {
      window.removeEventListener('auth:unauthorized', handleUnauthorized)
    }
  }, [loading, isAuthenticated, location.pathname, navigate, dispatch])

  const handleSignOut = async () => {
    await dispatch(logoutUser())
    startTransition(() => {
      navigate('/login')
    })
  }

  const NavItem = ({ icon, text, to }: { icon: any, text: string, to: string, active?: boolean }) => {
    const location = useLocation()
    const isActive = location.pathname === to

    const handleClick = () => {
      // Close sidebar on mobile when navigating
      setIsSidebarOpen(false)
    }

    return (
      <Link
        to={to}
        onClick={handleClick}
        className={`flex items-center gap-3 px-6 py-3 text-sm font-medium transition-colors duration-200 ${isActive
          ? 'bg-lb-red-primary text-white border-r-4 border-lb-yellow'
          : 'text-gray-300 hover:bg-gray-800 hover:text-lb-yellow'
          }`}
      >
        {icon}
        <span>{text}</span>
      </Link>
    )
  }

  // Auto-close sidebar on route change (mobile)
  useEffect(() => {
    setIsSidebarOpen(false)
  }, [location.pathname])


  // Show loading state while checking auth
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-lb-red-primary"></div>
      </div>
    )
  }

  // If not authenticated and not on login page, Login will be rendered
  // If authenticated and on login page, will be redirected to / automatically via useEffect
  if (!isAuthenticated && location.pathname === '/login') {
    return <Login />
  }

  if (!isAuthenticated) {
    return null // Will redirect to /login via useEffect
  }

  const getPageTitle = (pathname: string) => {
    switch (pathname) {
      case '/': return 'Overview';
      case '/appointments': return 'Appointments';
      case '/services': return 'Services';
      case '/settings': return 'Settings';
      case '/repairs': return 'My Repairs';
      case '/admin/ivr': return 'IVR Settings';
      case '/admin/customers': return 'Customers';
      case '/admin/staff': return 'Staff & Schedule';
      case '/wallboard/calendar': return 'Calendar';
      default:
        if (pathname.startsWith('/cases/')) return 'Case Details';
        return 'Dashboard';
    }
  };

  // User is authenticated - show dashboard
  // Check if we're in kiosk mode (customer-facing, no sidebar/header)
  const isKioskMode = location.pathname === '/checkin'
  const isWallboardMode = location.pathname === '/wallboard/calendar'

  return (
    <div className="min-h-screen bg-gray-100">
      <Toaster position="top-right" />

      {/* Mobile Overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar - Responsive Classes - Hidden in kiosk/wallboard modes */}
      {!isKioskMode && !isWallboardMode && (
        <div className={`
          fixed top-0 left-0 min-h-screen w-64 bg-lb-dark-gray border-r border-gray-700 z-30
          transform transition-transform duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}>
          <div className="p-6">
            <div className="flex items-center gap-3 mb-8">
              <div className="bg-lb-red-primary p-2 rounded-lg">
                <Wrench className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white tracking-wider font-heading">LB AUTO</h1>
                <p className="text-xs text-[#FDB80E] font-medium tracking-wide">REPAIR SERVICES</p>
              </div>
            </div>
            <nav className="space-y-1">
              <NavItem icon={<LayoutDashboard className="h-5 w-5" />} text="Overview" to="/" />
              <NavItem icon={<Calendar className="h-5 w-5" />} text="Appointments" to="/appointments" />
              <NavItem icon={<Settings className="h-5 w-5" />} text="Settings" to="/settings" />

              {(user?.staff_id || user?.is_admin) && (
                <NavItem icon={<Wrench className="h-5 w-5" />} text="My Repairs" to="/repairs" />
              )}

              {user?.is_admin && (
                <>
                  <div className="pt-4 pb-2 px-6 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Admin
                  </div>
                  <NavItem icon={<Tool className="h-5 w-5" />} text="Services" to="/services" />
                  <NavItem icon={<Tool className="h-5 w-5" />} text="Launch Kiosk" to="/checkin" />
                  <NavItem icon={<Phone className="h-5 w-5" />} text="IVR Settings" to="/admin/ivr" />
                  <NavItem icon={<Users className="h-5 w-5" />} text="Customers" to="/admin/customers" />
                  <NavItem icon={<Users className="h-5 w-5" />} text="Staff & Schedule" to="/admin/staff" />
                </>
              )}
            </nav>
          </div>
          <div className="absolute bottom-0 w-full p-6 border-t border-[#374151]">
            <button
              type="button"
              onClick={handleSignOut}
              className="flex w-full items-center gap-3 text-gray-400 hover:text-lb-yellow transition-colors focus:outline-none focus:ring-2 focus:ring-lb-yellow focus:ring-offset-2 focus:ring-offset-lb-dark-gray rounded p-2 -m-2"
            >
              <LogOut className="h-5 w-5" />
              <span className="text-sm font-medium">Sign Out</span>
            </button>
          </div>
        </div>
      )}

      <div className={(isKioskMode || isWallboardMode) ? '' : 'lg:pl-64 flex flex-col min-h-screen'}>
        {!isKioskMode && !isWallboardMode && (
          <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
          <div className="flex items-center justify-between px-4 sm:px-6 py-4">
            <div className="flex items-center gap-4">
              {/* Hamburger Menu Button */}
              <button
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                className="lg:hidden p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                <div className="space-y-1.5">
                  <span className="block w-6 h-0.5 bg-current"></span>
                  <span className="block w-6 h-0.5 bg-current"></span>
                  <span className="block w-6 h-0.5 bg-current"></span>
                </div>
              </button>

              <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white truncate">
                {getPageTitle(location.pathname)}
              </h1>
            </div>

            <div className="flex items-center gap-4">
              <span className="hidden sm:inline-block text-sm text-gray-600 dark:text-gray-300">
                {user?.username}
              </span>
              <button
                onClick={handleSignOut}
                className="p-2 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 transition-colors"
                title="Sign Out"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
          </header>
        )}

        <main className="flex-1 overflow-x-hidden overflow-y-auto bg-gray-50 dark:bg-gray-900 p-4 sm:p-8">
          <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
              <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/appointments" element={<Appointments />} />
              <Route path="/services" element={user?.is_admin ? <Services /> : <Navigate to="/" replace />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/repairs" element={<StaffDashboard />} />
              <Route path="/cases/:id" element={<CaseDetails />} />
              <Route path="/checkin" element={user?.is_admin ? <CheckIn /> : <Navigate to="/" replace />} />
              <Route path="/wallboard/calendar" element={<Appointments />} />
              <Route path="/admin/ivr" element={user?.is_admin ? <AdminIVR /> : <Navigate to="/" />} />
              <Route path="/admin/customers" element={user?.is_admin ? <AdminCustomers /> : <Navigate to="/" />} />
              <Route path="/admin/staff" element={user?.is_admin ? <AdminStaff /> : <Navigate to="/" />} />
              <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}

export default App