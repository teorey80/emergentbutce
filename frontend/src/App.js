import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';
import { PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar } from 'recharts';
import { useDropzone } from 'react-dropzone';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [expenses, setExpenses] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [stats, setStats] = useState({ total_amount: 0, expense_count: 0, category_stats: {} });
  const [monthlyStats, setMonthlyStats] = useState([]);
  const [trendStats, setTrendStats] = useState([]);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [uploadStatus, setUploadStatus] = useState('');
  
  // Filter states
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    search: '',
    category: 'all',
    minAmount: '',
    maxAmount: '',
    startDate: '',
    endDate: ''
  });
  const [filteredExpenses, setFilteredExpenses] = useState([]);
  const [filterSummary, setFilterSummary] = useState(null);
  const [isFiltering, setIsFiltering] = useState(false);
  
  // Mobile states
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [showMobileNav, setShowMobileNav] = useState(false);
  const [pullToRefresh, setPullToRefresh] = useState(false);
  const [touchStart, setTouchStart] = useState(0);
  const [touchEnd, setTouchEnd] = useState(0);
  
  // Smart features states
  const [insights, setInsights] = useState([]);
  const [predictions, setPredictions] = useState({});
  const [expenseLimits, setExpenseLimits] = useState({});
  const [limitWarnings, setLimitWarnings] = useState([]);
  const [showInsights, setShowInsights] = useState(false);
  
  // Interactive dashboard states
  const [selectedMonth, setSelectedMonth] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [interactiveExpenses, setInteractiveExpenses] = useState([]);

  // Form states
  const [formData, setFormData] = useState({
    title: '',
    amount: '',
    category: '',
    description: '',
    date: new Date().toISOString().split('T')[0]
  });

  // Fetch categories
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await axios.get(`${API}/categories`);
        setCategories(response.data);
      } catch (error) {
        console.error('Error fetching categories:', error);
      }
    };
    fetchCategories();
  }, []);

  // Fetch expenses
  const fetchExpenses = async () => {
    try {
      const response = await axios.get(`${API}/expenses`);
      setExpenses(response.data);
    } catch (error) {
      console.error('Error fetching expenses:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch all stats
  const fetchAllStats = async () => {
    try {
      const [statsResponse, monthlyResponse, trendsResponse] = await Promise.all([
        axios.get(`${API}/expenses/stats/summary`),
        axios.get(`${API}/expenses/stats/monthly`),
        axios.get(`${API}/expenses/stats/trends`)
      ]);
      
      setStats(statsResponse.data);
      setMonthlyStats(monthlyResponse.data);
      setTrendStats(trendsResponse.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  // Fetch smart insights
  const fetchSmartFeatures = async () => {
    try {
      const [insightsResponse, predictionsResponse, limitsResponse] = await Promise.all([
        axios.get(`${API}/expenses/insights`),
        axios.get(`${API}/expenses/predictions`),
        axios.get(`${API}/expenses/limits/check`)
      ]);
      
      setInsights(insightsResponse.data.insights || []);
      setPredictions(predictionsResponse.data.predictions || {});
      setLimitWarnings(limitsResponse.data.warnings || []);
    } catch (error) {
      console.error('Error fetching smart features:', error);
    }
  };

  useEffect(() => {
    fetchExpenses();
    fetchAllStats();
    fetchSmartFeatures();
    // Initialize filtered expenses
    setFilteredExpenses(expenses);
    
    // Check mobile on resize
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Update filtered expenses when expenses change
  useEffect(() => {
    if (!showFilters) {
      setFilteredExpenses(expenses);
    }
  }, [expenses, showFilters]);

  // Handle filter changes
  const handleFilterChange = (key, value) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }));
  };

  // Apply filters
  const applyFilters = async () => {
    try {
      setIsFiltering(true);
      const params = new URLSearchParams();
      
      if (filters.search) params.append('search', filters.search);
      if (filters.category !== 'all') params.append('category', filters.category);
      if (filters.minAmount) params.append('min_amount', filters.minAmount);
      if (filters.maxAmount) params.append('max_amount', filters.maxAmount);
      if (filters.startDate) params.append('start_date', filters.startDate);
      if (filters.endDate) params.append('end_date', filters.endDate);

      const response = await axios.get(`${API}/expenses/search?${params}`);
      setFilteredExpenses(response.data);

      // Get summary for filtered data
      const summaryParams = new URLSearchParams();
      if (filters.category !== 'all') summaryParams.append('category', filters.category);
      if (filters.startDate) summaryParams.append('start_date', filters.startDate);
      if (filters.endDate) summaryParams.append('end_date', filters.endDate);

      const summaryResponse = await axios.get(`${API}/expenses/summary?${summaryParams}`);
      setFilterSummary(summaryResponse.data);

    } catch (error) {
      console.error('Error applying filters:', error);
    } finally {
      setIsFiltering(false);
    }
  };

  // Clear filters
  const clearFilters = () => {
    setFilters({
      search: '',
      category: 'all',
      minAmount: '',
      maxAmount: '',
      startDate: '',
      endDate: ''
    });
    setFilteredExpenses(expenses);
    setFilterSummary(null);
    setIsFiltering(false);
  };

  // Manual filter trigger (for button click)
  const handleApplyFilters = (e) => {
    e.preventDefault();
    applyFilters();
  };

  // Auto-apply filters with debounce (optional)
  useEffect(() => {
    if (showFilters) {
      const timeoutId = setTimeout(() => {
        // Only auto-apply if user is not actively typing
        applyFilters();
      }, 1000); // Increased debounce time
      return () => clearTimeout(timeoutId);
    }
  }, [filters, showFilters]);
  
  // Mobile touch handlers
  const handleTouchStart = (e) => {
    setTouchEnd(0); // Reset touchEnd
    setTouchStart(e.targetTouches[0].clientX);
  };

  const handleTouchMove = (e) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > 50;
    const isRightSwipe = distance < -50;

    if (isLeftSwipe && activeTab === 'dashboard') {
      setActiveTab('expenses');
    } else if (isRightSwipe && activeTab === 'expenses') {
      setActiveTab('dashboard');
    } else if (isLeftSwipe && activeTab === 'expenses') {
      setActiveTab('analytics');
    } else if (isRightSwipe && activeTab === 'analytics') {
      setActiveTab('expenses');
    }
  };

  // Pull to refresh
  const handlePullToRefresh = async () => {
    setPullToRefresh(true);
    await fetchExpenses();
    await fetchAllStats();
    setTimeout(() => setPullToRefresh(false), 1000);
  };

  // Quick actions
  const quickActions = [
    { id: 'today', label: '📅 Bugün', action: () => {
      const today = new Date().toISOString().split('T')[0];
      handleFilterChange('startDate', today);
      handleFilterChange('endDate', today);
      setShowFilters(true);
    }},
    { id: 'week', label: '📊 Bu Hafta', action: () => {
      const today = new Date();
      const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
      handleFilterChange('startDate', weekAgo.toISOString().split('T')[0]);
      handleFilterChange('endDate', today.toISOString().split('T')[0]);
      setShowFilters(true);
    }},
    { id: 'food', label: '🍽️ Yiyecek', action: () => {
      handleFilterChange('category', 'food');
      setShowFilters(true);
    }},
    { id: 'transport', label: '🚗 Ulaşım', action: () => {
      handleFilterChange('category', 'transport');
      setShowFilters(true);
    }},
    { id: 'shopping', label: '🛍️ Alışveriş', action: () => {
      handleFilterChange('category', 'shopping');
      setShowFilters(true);
    }}
  ];

  // Handle form input changes
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const expenseData = {
        title: formData.title.trim(),
        amount: parseFloat(formData.amount),
        category: formData.category,
        description: formData.description ? formData.description.trim() : null,
        date: formData.date
      };
      
      console.log('Sending expense data:', expenseData);
      
      const response = await axios.post(`${API}/expenses`, expenseData);
      console.log('Response:', response.data);
      
      // Reset form
      setFormData({
        title: '',
        amount: '',
        category: '',
        description: '',
        date: new Date().toISOString().split('T')[0]
      });
      
      setShowAddForm(false);
      fetchExpenses();
      fetchAllStats();
    } catch (error) {
      console.error('Error creating expense:', error);
      if (error.response) {
        console.error('Error response:', error.response.data);
        alert(`Harcama eklenirken bir hata oluştu: ${error.response.data.detail || error.response.data.message || 'Bilinmeyen hata'}`);
      } else {
        alert('Harcama eklenirken bir hata oluştu');
      }
    }
  };

  // Delete expense
  const deleteExpense = async (expenseId) => {
    if (window.confirm('Bu harcamayı silmek istediğinize emin misiniz?')) {
      try {
        await axios.delete(`${API}/expenses/${expenseId}`);
        fetchExpenses();
        fetchAllStats();
      } catch (error) {
        console.error('Error deleting expense:', error);
        alert('Harcama silinirken bir hata oluştu');
      }
    }
  };

  // File upload handlers
  const onDrop = async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploadStatus('Yükleniyor...');
      let endpoint = '';
      
      if (file.name.endsWith('.csv')) {
        endpoint = '/upload/csv';
      } else if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
        endpoint = '/upload/excel';
      } else if (file.name.endsWith('.pdf')) {
        endpoint = '/upload/pdf';
      } else {
        throw new Error('Desteklenmeyen dosya formatı');
      }

      const response = await axios.post(`${API}${endpoint}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      console.log('Upload response:', response.data);

      // Show detailed results
      let statusMessage = `✅ ${response.data.message}`;
      
      if (response.data.auto_categorization) {
        statusMessage += '\n\n🤖 Otomatik Kategorilendirme:';
        Object.entries(response.data.auto_categorization).forEach(([category, items]) => {
          const categoryInfo = getCategoryInfo(category);
          statusMessage += `\n${categoryInfo.icon} ${categoryInfo.name}: ${items.length} harcama`;
        });
      }

      if (response.data.detected_columns) {
        statusMessage += '\n\n📋 Tespit Edilen Sütunlar:';
        Object.entries(response.data.detected_columns).forEach(([field, column]) => {
          statusMessage += `\n• ${field}: ${column}`;
        });
      }

      if (response.data.errors && response.data.errors.length > 0) {
        statusMessage += `\n\n⚠️ Hatalar:\n${response.data.errors.slice(0, 3).join('\n')}`;
        if (response.data.errors.length > 3) {
          statusMessage += `\n... ve ${response.data.errors.length - 3} hata daha`;
        }
      }

      setUploadStatus(statusMessage);
      
      // Refresh data if expenses were added
      if (response.data.imported > 0 || response.data.auto_added > 0) {
        fetchExpenses();
        fetchAllStats();
      }
      
      setTimeout(() => {
        setUploadStatus('');
        setShowImportModal(false);
      }, 8000);

    } catch (error) {
      console.error('Error uploading file:', error);
      let errorMessage = `❌ Hata: ${error.response?.data?.detail || error.message}`;
      
      if (error.response?.data?.errors) {
        errorMessage += `\n\nDetaylı Hatalar:\n${error.response.data.errors.slice(0, 3).join('\n')}`;
      }
      
      setUploadStatus(errorMessage);
      
      setTimeout(() => {
        setUploadStatus('');
      }, 10000);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/pdf': ['.pdf']
    },
    multiple: false
  });

  // Get category info
  const getCategoryInfo = (categoryId) => {
    return categories.find(cat => cat.id === categoryId) || { name: 'Bilinmeyen', color: '#A0A0A0', icon: '❓' };
  };

  // Format currency
  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('tr-TR', {
      style: 'currency',
      currency: 'TRY'
    }).format(amount);
  };

  // Format date
  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('tr-TR');
  };

  // Handle interactive dashboard clicks
  const handleMonthClick = async (data) => {
    if (data && data.activeLabel) {
      setSelectedMonth(data.activeLabel);
      setSelectedCategory(null); // Clear category selection
      
      // Find the month data and filter expenses
      const monthData = monthlyStats.find(m => m.month === data.activeLabel);
      if (monthData) {
        // Filter expenses by month
        const monthExpenses = expenses.filter(expense => {
          const expenseDate = new Date(expense.date);
          const expenseMonth = expenseDate.toLocaleDateString('tr-TR', { month: 'long', year: 'numeric' });
          return expenseMonth === data.activeLabel;
        });
        setInteractiveExpenses(monthExpenses);
      }
    }
  };

  const handleCategoryClick = (data) => {
    if (data && data.name) {
      setSelectedCategory(data.name);
      setSelectedMonth(null); // Clear month selection
      
      // Find category ID from name
      const categoryInfo = categories.find(cat => cat.name === data.name);
      if (categoryInfo) {
        // Filter expenses by category
        const categoryExpenses = expenses.filter(expense => expense.category === categoryInfo.id);
        setInteractiveExpenses(categoryExpenses);
      }
    }
  };

  const clearInteractiveSelection = () => {
    setSelectedMonth(null);
    setSelectedCategory(null);
    setInteractiveExpenses([]);
  };

  // Prepare chart data
  const pieChartData = Object.entries(stats.category_stats).map(([categoryId, stat]) => ({
    name: stat.name,
    value: stat.total,
    color: stat.color
  }));

  const monthlyChartData = monthlyStats.map(month => ({
    name: month.month,
    amount: month.total,
    count: month.count
  }));

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Yükleniyor...</p>
        </div>
      </div>
    );
  }

  return (
    <div 
      className="min-h-screen bg-gray-50"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Header */}
      <div className="bg-white shadow-sm border-b sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className={`flex justify-between items-center ${isMobile ? 'py-3' : 'py-6'}`}>
            <div className="flex items-center">
              <h1 className={`font-bold text-gray-900 ${isMobile ? 'text-xl' : 'text-3xl'}`}>
                💰 Harcama Takip
              </h1>
            </div>
            <div className={`flex space-x-2 ${isMobile ? 'space-x-1' : 'space-x-3'}`}>
              <button
                onClick={() => setShowImportModal(true)}
                className={`bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-colors ${
                  isMobile ? 'py-2 px-3 text-sm' : 'py-2 px-4'
                }`}
              >
                {isMobile ? '📁' : '📁 Dosya İçe Aktar'}
              </button>
              <button
                onClick={() => setShowAddForm(true)}
                className={`bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors ${
                  isMobile ? 'py-2 px-3 text-sm' : 'py-2 px-4'
                }`}
              >
                {isMobile ? '+' : '+ Harcama Ekle'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Quick Actions */}
      {isMobile && (
        <div className="bg-white border-b">
          <div className="quick-actions">
            {quickActions.map((action) => (
              <button
                key={action.id}
                onClick={action.action}
                className="quick-action-item"
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="bg-white border-b sticky top-16 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className={`flex ${isMobile ? 'overflow-x-auto mobile-nav-tabs' : 'space-x-8'}`}>
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`${isMobile ? 'mobile-nav-tab' : 'py-4 px-1 border-b-2 font-medium text-sm'} ${
                activeTab === 'dashboard' 
                  ? (isMobile ? 'active' : 'border-blue-500 text-blue-600')
                  : (isMobile ? '' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300')
              }`}
            >
              📊 Dashboard
            </button>
            <button
              onClick={() => setActiveTab('expenses')}
              className={`${isMobile ? 'mobile-nav-tab' : 'py-4 px-1 border-b-2 font-medium text-sm'} ${
                activeTab === 'expenses' 
                  ? (isMobile ? 'active' : 'border-blue-500 text-blue-600')
                  : (isMobile ? '' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300')
              }`}
            >
              📋 Harcamalar
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={`${isMobile ? 'mobile-nav-tab' : 'py-4 px-1 border-b-2 font-medium text-sm'} ${
                activeTab === 'analytics' 
                  ? (isMobile ? 'active' : 'border-blue-500 text-blue-600')
                  : (isMobile ? '' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300')
              }`}
            >
              📈 Analitik
            </button>
          </nav>
        </div>
      </div>

      {/* Pull to Refresh Indicator */}
      {pullToRefresh && (
        <div className="pull-to-refresh visible">
          <div className="animate-spin">🔄</div>
        </div>
      )}

      {/* Main Content */}
      <div className={`max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 ${isMobile ? 'py-4 pb-20' : 'py-8'}`}>
        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <div>
            {/* Hero Section */}
            <div className={`bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg mb-8 ${isMobile ? 'mobile-hero' : ''}`}>
              <div className={`grid grid-cols-1 ${isMobile ? '' : 'lg:grid-cols-2'} gap-8 items-center p-8`}>
                <div>
                  <h2 className={`font-bold mb-4 ${isMobile ? 'text-2xl' : 'text-4xl'}`}>Harcamalarınızı Kontrol Edin</h2>
                  <p className={`mb-6 ${isMobile ? 'text-base' : 'text-xl'}`}>Günlük harcamalarınızı takip edin, kategorilere ayırın ve mali durumunuzu analiz edin.</p>
                  <div className={`grid grid-cols-2 gap-4 ${isMobile ? 'mobile-stats' : ''}`}>
                    <div className="bg-white/20 backdrop-blur-sm rounded-lg p-4">
                      <div className={`font-bold ${isMobile ? 'text-lg' : 'text-2xl'}`}>{formatCurrency(stats.total_amount)}</div>
                      <div className={`opacity-90 ${isMobile ? 'text-xs' : 'text-sm'}`}>Toplam Harcama</div>
                    </div>
                    <div className="bg-white/20 backdrop-blur-sm rounded-lg p-4">
                      <div className={`font-bold ${isMobile ? 'text-lg' : 'text-2xl'}`}>{stats.expense_count}</div>
                      <div className={`opacity-90 ${isMobile ? 'text-xs' : 'text-sm'}`}>Toplam İşlem</div>
                    </div>
                  </div>
                </div>
                {!isMobile && (
                  <div className="flex justify-center">
                    <img 
                      src="https://images.pexels.com/photos/7789849/pexels-photo-7789849.jpeg" 
                      alt="Financial Dashboard" 
                      className="rounded-lg shadow-2xl max-w-md w-full"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Smart Insights Section */}
            {insights.length > 0 && (
              <div className="mb-8">
                <div className="flex justify-between items-center mb-6">
                  <h3 className={`font-bold text-gray-900 ${isMobile ? 'text-xl' : 'text-2xl'}`}>🤖 Akıllı İçgörüler</h3>
                  <button
                    onClick={() => setShowInsights(!showInsights)}
                    className="text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {showInsights ? 'Gizle' : 'Tümünü Göster'}
                  </button>
                </div>
                
                <div className={`grid gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-2'}`}>
                  {(showInsights ? insights : insights.slice(0, 2)).map((insight, index) => (
                    <div 
                      key={index}
                      className={`p-4 rounded-lg border-l-4 ${
                        insight.type === 'warning' ? 'bg-red-50 border-red-400' :
                        insight.type === 'success' ? 'bg-green-50 border-green-400' :
                        'bg-blue-50 border-blue-400'
                      }`}
                    >
                      <h4 className={`font-semibold mb-2 ${isMobile ? 'text-sm' : 'text-base'}`}>{insight.title}</h4>
                      <p className={`text-gray-700 mb-2 ${isMobile ? 'text-xs' : 'text-sm'}`}>{insight.message}</p>
                      <p className={`text-gray-600 font-medium ${isMobile ? 'text-xs' : 'text-sm'}`}>💡 {insight.suggestion}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Limit Warnings */}
            {limitWarnings.length > 0 && (
              <div className="mb-8">
                <h3 className={`font-bold text-gray-900 mb-4 ${isMobile ? 'text-xl' : 'text-2xl'}`}>⚠️ Limit Uyarıları</h3>
                <div className={`grid gap-3 ${isMobile ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-2'}`}>
                  {limitWarnings.map((warning, index) => (
                    <div key={index} className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <span className="text-2xl mr-3">{warning.icon}</span>
                          <div>
                            <h4 className={`font-semibold text-yellow-800 ${isMobile ? 'text-sm' : 'text-base'}`}>
                              {warning.category_name}
                            </h4>
                            <p className={`text-yellow-700 ${isMobile ? 'text-xs' : 'text-sm'}`}>
                              {warning.warning_type === 'approaching_limit' 
                                ? `Limite yaklaşıyorsunuz (%${warning.percentage.toFixed(0)})`
                                : `Limit aşıldı! ${formatCurrency(warning.exceeded_by)} fazla`
                              }
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`font-bold ${isMobile ? 'text-sm' : 'text-base'}`}>
                            {formatCurrency(warning.current)} / {formatCurrency(warning.limit)}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Predictions Section */}
            {Object.keys(predictions).length > 0 && (
              <div className="mb-8">
                <h3 className={`font-bold text-gray-900 mb-6 ${isMobile ? 'text-xl' : 'text-2xl'}`}>🔮 Gelecek Ay Tahminleri</h3>
                <div className={`grid gap-4 ${isMobile ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'}`}>
                  {Object.entries(predictions).map(([categoryId, prediction]) => (
                    <div key={categoryId} className="bg-white rounded-lg shadow-sm p-4 border">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <span className={`mr-3 ${isMobile ? 'text-xl' : 'text-2xl'}`}>{prediction.icon}</span>
                          <div>
                            <div className={`font-medium text-gray-900 ${isMobile ? 'text-sm' : ''}`}>
                              {prediction.category_name}
                            </div>
                            <div className={`text-gray-500 ${isMobile ? 'text-xs' : 'text-sm'}`}>
                              Güven: %{prediction.confidence.toFixed(0)}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`font-bold text-blue-600 ${isMobile ? 'text-sm' : ''}`}>
                            {formatCurrency(prediction.predicted_amount)}
                          </div>
                          <div className={`text-gray-500 ${isMobile ? 'text-xs' : 'text-sm'}`}>
                            Ort: {formatCurrency(prediction.historical_average)}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Category Stats */}
            {Object.keys(stats.category_stats).length > 0 && (
              <div className="mb-8">
                <h3 className={`font-bold text-gray-900 mb-6 ${isMobile ? 'text-xl' : 'text-2xl'}`}>Kategori Dağılımı</h3>
                <div className={`grid gap-4 ${isMobile ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4'}`}>
                  {Object.entries(stats.category_stats).map(([categoryId, stat]) => (
                    <div key={categoryId} className={`bg-white rounded-lg shadow-sm p-4 border ${isMobile ? 'mobile-card' : ''}`}>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <span className={`mr-3 ${isMobile ? 'text-xl' : 'text-2xl'}`}>{stat.icon}</span>
                          <div>
                            <div className={`font-medium text-gray-900 ${isMobile ? 'text-sm' : ''}`}>{stat.name}</div>
                            <div className={`text-gray-500 ${isMobile ? 'text-xs' : 'text-sm'}`}>{stat.count} işlem</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`font-bold text-gray-900 ${isMobile ? 'text-sm' : ''}`}>{formatCurrency(stat.total)}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Interactive Expenses Display */}
            {interactiveExpenses.length > 0 && (
              <div className="mb-8">
                <div className="bg-white rounded-lg shadow-sm">
                  <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                    <h3 className={`font-semibold text-gray-900 ${isMobile ? 'text-lg' : 'text-xl'}`}>
                      {selectedMonth && `📅 ${selectedMonth} Harcamaları`}
                      {selectedCategory && `📊 ${selectedCategory} Harcamaları`}
                    </h3>
                    <div className="flex items-center space-x-3">
                      <span className="text-sm text-gray-500">
                        {interactiveExpenses.length} harcama • {formatCurrency(interactiveExpenses.reduce((sum, exp) => sum + exp.amount, 0))}
                      </span>
                      <button
                        onClick={clearInteractiveSelection}
                        className="text-red-600 hover:text-red-800 text-sm font-medium"
                      >
                        ✖️ Kapat
                      </button>
                    </div>
                  </div>
                  
                  <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
                    {interactiveExpenses.map((expense) => {
                      const categoryInfo = getCategoryInfo(expense.category);
                      return (
                        <div key={expense.id} className="p-4 hover:bg-gray-50 transition-colors">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center">
                              <div 
                                className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold mr-3 ${isMobile ? 'w-8 h-8 text-sm' : ''}`}
                                style={{ backgroundColor: categoryInfo.color }}
                              >
                                {categoryInfo.icon}
                              </div>
                              <div>
                                <h4 className={`font-medium text-gray-900 ${isMobile ? 'text-sm' : 'text-base'}`}>{expense.title}</h4>
                                <p className={`text-gray-500 ${isMobile ? 'text-xs' : 'text-sm'}`}>
                                  {categoryInfo.name} • {formatDate(expense.date)}
                                </p>
                                {expense.description && (
                                  <p className={`text-gray-600 mt-1 ${isMobile ? 'text-xs' : 'text-sm'}`}>{expense.description}</p>
                                )}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className={`font-bold text-gray-900 ${isMobile ? 'text-sm' : 'text-lg'}`}>
                                {formatCurrency(expense.amount)}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* Charts */}
            {pieChartData.length > 0 && (
              <div className={`grid gap-8 mb-8 ${isMobile ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-2'}`}>
                <div className="bg-white rounded-lg shadow-sm p-6">
                  <h3 className={`font-semibold text-gray-900 mb-4 ${isMobile ? 'text-lg' : 'text-xl'}`}>Kategori Dağılımı</h3>
                  <ResponsiveContainer width="100%" height={isMobile ? 250 : 300}>
                    <PieChart>
                      <Pie
                        data={pieChartData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        outerRadius={isMobile ? 60 : 80}
                        fill="#8884d8"
                        dataKey="value"
                        onClick={handleCategoryClick}
                        style={{ cursor: 'pointer' }}
                      >
                        {pieChartData.map((entry, index) => (
                          <Cell 
                            key={`cell-${index}`} 
                            fill={entry.color}
                            style={{ cursor: 'pointer' }}
                          />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => formatCurrency(value)} />
                    </PieChart>
                  </ResponsiveContainer>
                  {selectedCategory && (
                    <div className="mt-2 text-center">
                      <p className="text-sm text-blue-600">📊 Seçili: {selectedCategory}</p>
                      <button 
                        onClick={clearInteractiveSelection}
                        className="text-xs text-gray-500 hover:text-gray-700"
                      >
                        Temizle
                      </button>
                    </div>
                  )}
                </div>

                {monthlyChartData.length > 0 && (
                  <div className="bg-white rounded-lg shadow-sm p-6">
                    <h3 className={`font-semibold text-gray-900 mb-4 ${isMobile ? 'text-lg' : 'text-xl'}`}>Aylık Harcamalar</h3>
                    <ResponsiveContainer width="100%" height={isMobile ? 250 : 300}>
                      <BarChart data={monthlyChartData} onClick={handleMonthClick}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" fontSize={isMobile ? 10 : 12} />
                        <YAxis fontSize={isMobile ? 10 : 12} />
                        <Tooltip formatter={(value) => formatCurrency(value)} />
                        <Bar 
                          dataKey="amount" 
                          fill="#3B82F6" 
                          style={{ cursor: 'pointer' }}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                    {selectedMonth && (
                      <div className="mt-2 text-center">
                        <p className="text-sm text-blue-600">📅 Seçili: {selectedMonth}</p>
                        <button 
                          onClick={clearInteractiveSelection}
                          className="text-xs text-gray-500 hover:text-gray-700"
                        >
                          Temizle
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Expenses Tab */}
        {activeTab === 'expenses' && (
          <div>
            {/* Filter Section */}
            <div className="bg-white rounded-lg shadow-sm mb-6">
              <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                <h3 className="text-xl font-semibold text-gray-900">Harcamalar</h3>
                <div className="flex space-x-3">
                  <button
                    onClick={() => setShowFilters(!showFilters)}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      showFilters 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    🔍 {showFilters ? 'Filtreleri Gizle' : 'Filtrele & Ara'}
                  </button>
                  {showFilters && (
                    <button
                      onClick={clearFilters}
                      className="px-4 py-2 bg-red-100 text-red-700 hover:bg-red-200 rounded-lg font-medium transition-colors"
                    >
                      ✖️ Temizle
                    </button>
                  )}
                </div>
              </div>
              
              {showFilters && (
                <div className="p-6 bg-gray-50">
                  <form onSubmit={handleApplyFilters}>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {/* Search */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          🔎 Metin Arama
                        </label>
                        <input
                          type="text"
                          value={filters.search}
                          onChange={(e) => handleFilterChange('search', e.target.value)}
                          placeholder="Harcama adı veya açıklama ara..."
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      
                      {/* Category Filter */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          📋 Kategori
                        </label>
                        <select
                          value={filters.category}
                          onChange={(e) => handleFilterChange('category', e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="all">Tüm Kategoriler</option>
                          {categories.map((category) => (
                            <option key={category.id} value={category.id}>
                              {category.icon} {category.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      
                      {/* Amount Range */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          💰 Tutar Aralığı
                        </label>
                        <div className="flex space-x-2">
                          <input
                            type="number"
                            value={filters.minAmount}
                            onChange={(e) => handleFilterChange('minAmount', e.target.value)}
                            placeholder="Min ₺"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <input
                            type="number"
                            value={filters.maxAmount}
                            onChange={(e) => handleFilterChange('maxAmount', e.target.value)}
                            placeholder="Max ₺"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                      </div>
                      
                      {/* Date Range */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          📅 Başlangıç Tarihi
                        </label>
                        <input
                          type="date"
                          value={filters.startDate}
                          onChange={(e) => handleFilterChange('startDate', e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          📅 Bitiş Tarihi
                        </label>
                        <input
                          type="date"
                          value={filters.endDate}
                          onChange={(e) => handleFilterChange('endDate', e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      
                      {/* Action Buttons */}
                      <div className="flex flex-col space-y-2">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          🎯 İşlemler
                        </label>
                        <button
                          type="submit"
                          disabled={isFiltering}
                          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium py-2 px-4 rounded-md transition-colors flex items-center justify-center"
                        >
                          {isFiltering ? (
                            <>
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                              Filtreleniyor...
                            </>
                          ) : (
                            '🔍 Filtrele'
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={clearFilters}
                          className="w-full bg-gray-600 hover:bg-gray-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
                        >
                          🗑️ Temizle
                        </button>
                      </div>
                    </div>
                    
                    {/* Quick Filters */}
                    <div className="mt-4">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        ⚡ Hızlı Filtreler
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            const today = new Date().toISOString().split('T')[0];
                            handleFilterChange('startDate', today);
                            handleFilterChange('endDate', today);
                          }}
                          className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm hover:bg-blue-200 transition-colors"
                        >
                          Bugün
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            const today = new Date();
                            const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
                            handleFilterChange('startDate', weekAgo.toISOString().split('T')[0]);
                            handleFilterChange('endDate', today.toISOString().split('T')[0]);
                          }}
                          className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm hover:bg-green-200 transition-colors"
                        >
                          Son 7 Gün
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            const today = new Date();
                            const monthAgo = new Date(today.getFullYear(), today.getMonth() - 1, today.getDate());
                            handleFilterChange('startDate', monthAgo.toISOString().split('T')[0]);
                            handleFilterChange('endDate', today.toISOString().split('T')[0]);
                          }}
                          className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm hover:bg-purple-200 transition-colors"
                        >
                          Son 30 Gün
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            handleFilterChange('category', 'food');
                          }}
                          className="px-3 py-1 bg-orange-100 text-orange-700 rounded-full text-sm hover:bg-orange-200 transition-colors"
                        >
                          🍽️ Yiyecek
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            handleFilterChange('category', 'transport');
                          }}
                          className="px-3 py-1 bg-teal-100 text-teal-700 rounded-full text-sm hover:bg-teal-200 transition-colors"
                        >
                          🚗 Ulaşım
                        </button>
                      </div>
                    </div>
                  </form>
                  
                  {/* Filter Summary */}
                  {filterSummary && (
                    <div className="mt-6 p-4 bg-white rounded-lg border">
                      <h4 className="font-medium text-gray-900 mb-3">📊 Filtreleme Sonuçları</h4>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold text-blue-600">{formatCurrency(filterSummary.total_amount)}</div>
                          <div className="text-sm text-gray-500">Toplam Tutar</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-green-600">{filterSummary.total_count}</div>
                          <div className="text-sm text-gray-500">Harcama Sayısı</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-purple-600">{formatCurrency(filterSummary.average_per_day)}</div>
                          <div className="text-sm text-gray-500">Günlük Ortalama</div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
            
            {/* Expenses List */}
            <div className="bg-white rounded-lg shadow-sm">
              {filteredExpenses.length === 0 ? (
                <div className="p-12 text-center">
                  {showFilters ? (
                    <>
                      <div className="text-6xl mb-4">🔍</div>
                      <h3 className="text-xl font-medium text-gray-900 mb-2">Filtreye uygun harcama bulunamadı</h3>
                      <p className="text-gray-500 mb-6">Farklı kriterler deneyin veya filtreleri temizleyin</p>
                      <button
                        onClick={clearFilters}
                        className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
                      >
                        Filtreleri Temizle
                      </button>
                    </>
                  ) : (
                    <>
                      <div className="text-6xl mb-4">📊</div>
                      <h3 className="text-xl font-medium text-gray-900 mb-2">Henüz harcama bulunmuyor</h3>
                      <p className="text-gray-500 mb-6">İlk harcamanızı ekleyerek başlayın</p>
                      <button
                        onClick={() => setShowAddForm(true)}
                        className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
                      >
                        Harcama Ekle
                      </button>
                    </>
                  )}
                </div>
              ) : (
                <div className="divide-y divide-gray-200">
                  {filteredExpenses.map((expense) => {
                    const categoryInfo = getCategoryInfo(expense.category);
                    return (
                      <div key={expense.id} className="p-6 hover:bg-gray-50 transition-colors">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center">
                            <div 
                              className="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg mr-4"
                              style={{ backgroundColor: categoryInfo.color }}
                            >
                              {categoryInfo.icon}
                            </div>
                            <div>
                              <h4 className="text-lg font-medium text-gray-900">{expense.title}</h4>
                              <p className="text-sm text-gray-500">{categoryInfo.name} • {formatDate(expense.date)}</p>
                              {expense.description && (
                                <p className="text-sm text-gray-600 mt-1">{expense.description}</p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center">
                            <div className="text-right mr-4">
                              <div className="text-xl font-bold text-gray-900">{formatCurrency(expense.amount)}</div>
                            </div>
                            <button
                              onClick={() => deleteExpense(expense.id)}
                              className="text-red-600 hover:text-red-800 p-2 rounded-full hover:bg-red-50 transition-colors"
                            >
                              🗑️
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <div className="space-y-8">
            {monthlyChartData.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm p-6">
                <h3 className="text-xl font-semibold text-gray-900 mb-4">Aylık Trend</h3>
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={monthlyChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip formatter={(value) => formatCurrency(value)} />
                    <Legend />
                    <Line type="monotone" dataKey="amount" stroke="#3B82F6" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {trendStats.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm p-6">
                <h3 className="text-xl font-semibold text-gray-900 mb-4">Kategori Trendleri</h3>
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip formatter={(value) => formatCurrency(value)} />
                    <Legend />
                    {trendStats.map((trend, index) => (
                      <Line
                        key={trend.category_id}
                        type="monotone"
                        dataKey="amount"
                        data={trend.data}
                        name={trend.category}
                        stroke={trend.color}
                        strokeWidth={2}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Dosya İçe Aktar</h3>
            </div>
            
            <div className="p-6">
              <div className="mb-4">
                <h4 className="font-medium text-gray-900 mb-2">Desteklenen Formatlar:</h4>
                <ul className="text-sm text-gray-600 space-y-1">
                  <li>• CSV: title, amount, category, description, date</li>
                  <li>• Excel: title, amount, category, description, date</li>
                  <li>• PDF: Fatura/makbuz okuma (deneysel)</li>
                </ul>
              </div>

              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
                }`}
              >
                <input {...getInputProps()} />
                <div className="text-4xl mb-4">📁</div>
                {isDragActive ? (
                  <p className="text-blue-600">Dosyayı buraya bırakın...</p>
                ) : (
                  <div>
                    <p className="text-gray-600 mb-2">Dosyayı sürükleyin veya tıklayın</p>
                    <p className="text-sm text-gray-500">CSV, Excel, PDF desteklenir</p>
                  </div>
                )}
              </div>

              {uploadStatus && (
                <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                  <p className="text-sm">{uploadStatus}</p>
                </div>
              )}
            </div>
            
            <div className="px-6 py-4 border-t border-gray-200">
              <button
                onClick={() => setShowImportModal(false)}
                className="w-full px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
              >
                Kapat
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Expense Modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Yeni Harcama Ekle</h3>
            </div>
            
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Harcama Adı
                </label>
                <input
                  type="text"
                  name="title"
                  value={formData.title}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Tutar (₺)
                </label>
                <input
                  type="number"
                  name="amount"
                  value={formData.amount}
                  onChange={handleInputChange}
                  step="0.01"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Kategori
                </label>
                <select
                  name="category"
                  value={formData.category}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Kategori seçin</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.icon} {category.name}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Tarih
                </label>
                <input
                  type="date"
                  name="date"
                  value={formData.date}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Açıklama (İsteğe bağlı)
                </label>
                <textarea
                  name="description"
                  value={formData.description}
                  onChange={handleInputChange}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div className="flex space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="flex-1 px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                >
                  İptal
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"
                >
                  Ekle
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;