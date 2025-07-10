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

  useEffect(() => {
    fetchExpenses();
    fetchAllStats();
  }, []);

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
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <h1 className="text-3xl font-bold text-gray-900">💰 Harcama Takip</h1>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => setShowImportModal(true)}
                className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
              >
                📁 Dosya İçe Aktar
              </button>
              <button
                onClick={() => setShowAddForm(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
              >
                + Harcama Ekle
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'dashboard' 
                ? 'border-blue-500 text-blue-600' 
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              📊 Dashboard
            </button>
            <button
              onClick={() => setActiveTab('expenses')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'expenses' 
                ? 'border-blue-500 text-blue-600' 
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              📋 Harcamalar
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'analytics' 
                ? 'border-blue-500 text-blue-600' 
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              📈 Analitik
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <div>
            {/* Hero Section */}
            <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg mb-8">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center p-8">
                <div>
                  <h2 className="text-4xl font-bold mb-4">Harcamalarınızı Kontrol Edin</h2>
                  <p className="text-xl mb-6">Günlük harcamalarınızı takip edin, kategorilere ayırın ve mali durumunuzu analiz edin.</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-white/20 backdrop-blur-sm rounded-lg p-4">
                      <div className="text-2xl font-bold">{formatCurrency(stats.total_amount)}</div>
                      <div className="text-sm opacity-90">Toplam Harcama</div>
                    </div>
                    <div className="bg-white/20 backdrop-blur-sm rounded-lg p-4">
                      <div className="text-2xl font-bold">{stats.expense_count}</div>
                      <div className="text-sm opacity-90">Toplam İşlem</div>
                    </div>
                  </div>
                </div>
                <div className="flex justify-center">
                  <img 
                    src="https://images.pexels.com/photos/7789849/pexels-photo-7789849.jpeg" 
                    alt="Financial Dashboard" 
                    className="rounded-lg shadow-2xl max-w-md w-full"
                  />
                </div>
              </div>
            </div>

            {/* Category Stats */}
            {Object.keys(stats.category_stats).length > 0 && (
              <div className="mb-8">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">Kategori Dağılımı</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {Object.entries(stats.category_stats).map(([categoryId, stat]) => (
                    <div key={categoryId} className="bg-white rounded-lg shadow-sm p-4 border">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <span className="text-2xl mr-3">{stat.icon}</span>
                          <div>
                            <div className="font-medium text-gray-900">{stat.name}</div>
                            <div className="text-sm text-gray-500">{stat.count} işlem</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold text-gray-900">{formatCurrency(stat.total)}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Charts */}
            {pieChartData.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                <div className="bg-white rounded-lg shadow-sm p-6">
                  <h3 className="text-xl font-semibold text-gray-900 mb-4">Kategori Dağılımı</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={pieChartData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {pieChartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => formatCurrency(value)} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {monthlyChartData.length > 0 && (
                  <div className="bg-white rounded-lg shadow-sm p-6">
                    <h3 className="text-xl font-semibold text-gray-900 mb-4">Aylık Harcamalar</h3>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={monthlyChartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip formatter={(value) => formatCurrency(value)} />
                        <Bar dataKey="amount" fill="#3B82F6" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Expenses Tab */}
        {activeTab === 'expenses' && (
          <div className="bg-white rounded-lg shadow-sm">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-xl font-semibold text-gray-900">Harcamalar</h3>
            </div>
            
            {expenses.length === 0 ? (
              <div className="p-12 text-center">
                <div className="text-6xl mb-4">📊</div>
                <h3 className="text-xl font-medium text-gray-900 mb-2">Henüz harcama bulunmuyor</h3>
                <p className="text-gray-500 mb-6">İlk harcamanızı ekleyerek başlayın</p>
                <button
                  onClick={() => setShowAddForm(true)}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
                >
                  Harcama Ekle
                </button>
              </div>
            ) : (
              <div className="divide-y divide-gray-200">
                {expenses.map((expense) => {
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