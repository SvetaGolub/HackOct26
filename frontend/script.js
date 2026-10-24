const API_BASE_URL = '/api/v1';

function isoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function startOfCurrentWeek() {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return date;
}

function invoiceKeeperApp() {
  const today = isoDate(new Date());

  return {
    theme: localStorage.getItem('app-theme') || 'light',
    defaultCurrency: 'RUB',
    weekdays: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
    departments: [],
    referenceTodayISO: today,
    startMonday: startOfCurrentWeek(),
    tableSearch: '',
    tableDeptFilter: '',
    tableStatusFilter: '',
    tableCurrencyFilter: '',
    showTableFilter: false,
    journalSearch: '',
    journalStatusFilter: '',
    isModalOpen: false,
    selectedDateISO: today,
    newRec: {
      description: '',
      department: '',
      amount: '',
      currency: 'RUB',
      periodicity: 'monthly',
      status: 'В ожидании',
      paidAt: ''
    },
    records: [],
    authToken: localStorage.getItem('invoice-keeper-token') || '',
    currentUser: null,
    departmentsById: {},
    departmentIdsByName: {},
    periodicityByRecurringId: {},

    get canManageRecurring() {
      return ['admin', 'accountant'].includes(this.currentUser?.role);
    },

    get isAdmin() {
      return this.currentUser?.role === 'admin';
    },

    get periodLabel() {
      const end = new Date(this.startMonday);
      end.setDate(end.getDate() + 13);
      const options = { month: 'long', year: 'numeric' };
      const startLabel = this.startMonday.toLocaleDateString('ru-RU', options);
      const endLabel = end.toLocaleDateString('ru-RU', options);
      return startLabel === endLabel ? startLabel : `${startLabel} — ${endLabel}`;
    },

    get calendarDays() {
      return Array.from({ length: 14 }, (_, index) => {
        const date = new Date(this.startMonday);
        date.setDate(date.getDate() + index);
        return {
          iso: isoDate(date),
          displayDate: date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
        };
      });
    },

    get filteredTableRecords() {
      const query = this.tableSearch.toLocaleLowerCase().trim();
      return this.records.filter(record => {
        const matchesQuery = !query || [
          record.description,
          record.department,
          record.employee
        ].some(value => String(value).toLocaleLowerCase().includes(query));
        return matchesQuery
          && (!this.tableDeptFilter || record.department === this.tableDeptFilter)
          && (!this.tableStatusFilter || record.status === this.tableStatusFilter)
          && (!this.tableCurrencyFilter || record.currency === this.tableCurrencyFilter);
      });
    },

    get filteredJournalRecords() {
      const query = this.journalSearch.toLocaleLowerCase().trim();
      return this.records.filter(record => {
        const matchesQuery = !query || [
          record.description,
          record.department,
          record.employee
        ].some(value => String(value).toLocaleLowerCase().includes(query));
        return matchesQuery && (!this.journalStatusFilter || record.status === this.journalStatusFilter);
      });
    },

    async apiRequest(path, method = 'GET', body = null) {
      const headers = {};
      if (body !== null) headers['Content-Type'] = 'application/json';
      if (this.authToken) headers.Authorization = `Bearer ${this.authToken}`;

      let response;
      try {
        response = await fetch(`${API_BASE_URL}${path}`, {
          method,
          headers,
          ...(body !== null ? { body: JSON.stringify(body) } : {})
        });
      } catch (error) {
        throw new Error(`Не удалось подключиться к API: ${error.message}`);
      }

      if (response.status === 204) return null;
      const contentType = response.headers.get('content-type') || '';
      const result = contentType.includes('application/json')
        ? await response.json()
        : await response.text();

      if (!response.ok) {
        const detail = result?.detail || result?.message || result;
        const message = Array.isArray(detail)
          ? detail.map(item => item.msg || JSON.stringify(item)).join('; ')
          : typeof detail === 'string' ? detail : JSON.stringify(detail);
        const error = new Error(`Ошибка API (${response.status}): ${message || response.statusText}`);
        error.status = response.status;
        throw error;
      }
      return result;
    },

    async login() {
      const email = window.prompt('Введите email для входа в Invoice Keeper:');
      if (!email) return false;
      const password = window.prompt('Введите пароль:');
      if (!password) return false;

      const result = await this.apiRequest('/auth/login', 'POST', { email, password });
      if (!result?.accessToken) throw new Error('API не вернул токен авторизации.');
      this.authToken = result.accessToken;
      localStorage.setItem('invoice-keeper-token', this.authToken);
      this.currentUser = result.user;
      return true;
    },

    async ensureAuthenticated() {
      if (this.authToken) {
        try {
          this.currentUser = await this.apiRequest('/auth/me');
          return true;
        } catch (error) {
          if (error.status !== 401) throw error;
          this.authToken = '';
          localStorage.removeItem('invoice-keeper-token');
        }
      }
      return this.login();
    },

    async fetchAll(path) {
      const items = [];
      const pageSize = 500;
      let offset = 0;
      let page;
      do {
        const separator = path.includes('?') ? '&' : '?';
        page = await this.apiRequest(`${path}${separator}limit=${pageSize}&offset=${offset}`);
        if (!Array.isArray(page)) throw new Error('API вернул неожиданный формат списка.');
        items.push(...page);
        offset += page.length;
      } while (page.length === pageSize);
      return items;
    },

    mapOccurrence(item) {
      const periodicity = this.periodicityByRecurringId[item.recurring_payment_id];
      const department = item.department?.name
        || this.departmentsById[item.department_id]
        || `Отдел ${item.department_id}`;
      return {
        id: item.id,
        recurringId: item.recurring_payment_id,
        dueDate: item.due_date,
        paidAt: item.paid_date || '',
        employee: 'Не указан',
        department,
        description: item.title,
        amount: Number(item.amount),
        currency: item.currency,
        periodicity: periodicity === 'one_time' ? 'Разовый' : 'Ежемесячно',
        status: item.is_paid ? 'Одобрено' : 'В ожидании',
        isOverdue: Boolean(item.is_overdue)
      };
    },

    async loadFromBackend() {
      const [departments, recurringPayments, occurrences] = await Promise.all([
        this.apiRequest('/departments'),
        this.fetchAll('/recurring-payments?include_inactive=true'),
        this.fetchAll('/payment-occurrences')
      ]);
      if (!Array.isArray(departments)) throw new Error('API вернул неожиданный формат списка отделов.');

      this.departmentsById = Object.fromEntries(departments.map(item => [item.id, item.name]));
      this.departmentIdsByName = Object.fromEntries(departments.map(item => [item.name, item.id]));
      this.departments = departments.map(item => item.name);
      this.periodicityByRecurringId = Object.fromEntries(
        recurringPayments.map(item => [item.id, item.periodicity])
      );
      if (!this.newRec.department && this.departments.length) {
        this.newRec.department = this.departments[0];
      }
      this.records = occurrences.map(item => this.mapOccurrence(item));
    },

    async init() {
      try {
        if (await this.ensureAuthenticated()) await this.loadFromBackend();
      } catch (error) {
        console.error('Не удалось загрузить данные Invoice Keeper:', error);
        window.alert(error.message);
      }
    },

    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light';
      localStorage.setItem('app-theme', this.theme);
    },

    shiftWeeks(days) {
      const next = new Date(this.startMonday);
      next.setDate(next.getDate() + days);
      this.startMonday = next;
    },

    getRecordsByDate(date) {
      return this.records.filter(record => record.dueDate === date);
    },

    isOverdue(item) {
      return item.paidAt
        ? item.paidAt > item.dueDate
        : this.referenceTodayISO > item.dueDate;
    },

    hasTelegramReminderSoon(date) {
      const daysUntilDue = Math.round(
        (new Date(`${date}T00:00:00`) - new Date(`${this.referenceTodayISO}T00:00:00`)) / 86400000
      );
      return daysUntilDue >= 0 && daysUntilDue <= 3
        && this.getRecordsByDate(date).some(record => record.status !== 'Одобрено');
    },

    async onStatusChange(item) {
      if (item.status === 'Отказано') {
        item.status = 'В ожидании';
        window.alert('API хранит только состояния «Оплачено» и «Не оплачено». Просрочка рассчитывается автоматически.');
      }
      if (item.status === 'Одобрено' && !item.paidAt) {
        item.paidAt = item.dueDate <= this.referenceTodayISO ? item.dueDate : this.referenceTodayISO;
      } else if (item.status !== 'Одобрено') {
        item.paidAt = '';
      }
      await this.syncOccurrenceWithDb(item);
    },

    async onActualDateChange(item) {
      item.status = item.paidAt ? 'Одобрено' : 'В ожидании';
      await this.syncOccurrenceWithDb(item);
    },

    async syncOccurrenceWithDb(item) {
      try {
        const body = item.paidAt
          ? { is_paid: true, paid_date: item.paidAt }
          : { is_paid: false };
        const result = await this.apiRequest(`/payment-occurrences/${item.id}`, 'PATCH', body);
        Object.assign(item, this.mapOccurrence(result));
      } catch (error) {
        console.error('Не удалось обновить статус платежа:', error);
        window.alert(error.message);
        try {
          await this.loadFromBackend();
        } catch (reloadError) {
          console.error('Не удалось обновить данные после ошибки:', reloadError);
          window.alert(reloadError.message);
        }
      }
    },

    summaryByCurrency(currency) {
      return this.records
        .filter(record => record.currency === currency)
        .reduce((sum, record) => sum + Number(record.amount || 0), 0);
    },

    getDayTotalsString(date) {
      const totals = {};
      this.getRecordsByDate(date).forEach(record => {
        totals[record.currency] = (totals[record.currency] || 0) + Number(record.amount);
      });
      return Object.entries(totals)
        .map(([currency, amount]) => `${amount.toLocaleString('ru-RU')} ${this.currencySymbol(currency)}`)
        .join(' | ');
    },

    cycleJournalFilter() {
      const order = ['', 'Одобрено', 'Отказано', 'В ожидании'];
      this.journalStatusFilter = order[(order.indexOf(this.journalStatusFilter) + 1) % order.length];
    },

    resetTableFilters() {
      this.tableSearch = '';
      this.tableDeptFilter = '';
      this.tableStatusFilter = '';
      this.tableCurrencyFilter = '';
    },

    openDayModal(date) {
      this.selectedDateISO = date;
      this.newRec.currency = this.defaultCurrency;
      this.newRec.paidAt = '';
      this.newRec.status = 'В ожидании';
      this.isModalOpen = true;
    },

    async createRecord() {
      if (!this.canManageRecurring) {
        window.alert('Создавать регулярные платежи могут бухгалтер и администратор.');
        return;
      }
      if (this.newRec.status === 'Отказано') {
        window.alert('API не поддерживает статус «Отказано» при создании платежа.');
        return;
      }
      const departmentId = this.departmentIdsByName[this.newRec.department]
        || this.currentUser?.department_id;
      if (!departmentId) {
        window.alert('Не удалось определить отдел для нового платежа.');
        return;
      }

      try {
        const recurring = await this.apiRequest('/recurring-payments', 'POST', {
          title: this.newRec.description.trim(),
          amount: Number(this.newRec.amount),
          currency: this.newRec.currency,
          first_due_date: this.selectedDateISO,
          periodicity: this.newRec.periodicity,
          department_id: departmentId
        });

        if (this.newRec.status === 'Одобрено') {
          const periods = await this.apiRequest(
            `/payment-occurrences?date_from=${this.selectedDateISO}&date_to=${this.selectedDateISO}&limit=500`
          );
          const period = periods.find(item => item.recurring_payment_id === recurring.id);
          if (!period) throw new Error('Платеж создан, но его период не найден для отметки оплаты.');
          const paidDate = this.newRec.paidAt
            || (this.selectedDateISO <= this.referenceTodayISO
              ? this.selectedDateISO
              : this.referenceTodayISO);
          await this.apiRequest(`/payment-occurrences/${period.id}`, 'PATCH', {
            is_paid: true,
            paid_date: paidDate
          });
        }

        this.isModalOpen = false;
        this.newRec.description = '';
        this.newRec.amount = '';
        this.newRec.paidAt = '';
        await this.loadFromBackend();
      } catch (error) {
        console.error('Не удалось создать платеж:', error);
        window.alert(error.message);
      }
    },

    async deleteRecord(occurrenceId) {
      if (!this.isAdmin) {
        window.alert('Прекращать регулярные платежи может только администратор.');
        return;
      }
      const record = this.records.find(item => item.id === occurrenceId);
      if (!record || !window.confirm('Прекратить регулярный платеж? История оплат сохранится.')) return;
      try {
        await this.apiRequest(`/recurring-payments/${record.recurringId}`, 'DELETE');
        await this.loadFromBackend();
      } catch (error) {
        console.error('Не удалось прекратить регулярный платеж:', error);
        window.alert(error.message);
      }
    },

    logout() {
      this.authToken = '';
      this.currentUser = null;
      this.records = [];
      localStorage.removeItem('invoice-keeper-token');
      window.location.reload();
    },

    statusColor(item) {
      if (this.isOverdue(item)) return 'rejected';
      if (item.status === 'Одобрено') return 'approved';
      return 'pending';
    },

    currencySymbol(code) {
      if (code === 'USD') return '$';
      if (code === 'EUR') return '€';
      return '₽';
    },

    formatMoney(amount, currency) {
      return `${Number(amount).toLocaleString('ru-RU')} ${this.currencySymbol(currency || this.defaultCurrency)}`;
    },

    formatReadableDate(value) {
      if (!value) return '';
      const [year, month, day] = value.split('-');
      return `${day}.${month}.${year}`;
    }
  };
}
