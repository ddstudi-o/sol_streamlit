# solar_widget.py

SOLAR_CALCULATOR_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: transparent; color: #333; padding: 10px; margin: 0; }
        .container { max-width: 100%; }
        .control-group { margin-bottom: 15px; background: rgba(255,255,255,0.8); padding: 12px; border-radius: 8px; border: 1px solid #e0e0e0; }
        label { display: block; font-weight: bold; margin-bottom: 6px; font-size: 14px; color: #444; }
        input[type="range"], select { width: 100%; padding: 6px; border-radius: 5px; border: 1px solid #ccc; box-sizing: border-box; }
        .val-display { float: right; color: #667eea; font-weight: bold; }
        .results { background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); padding: 15px; border-radius: 10px; border: 2px solid #2196f3; margin-top: 15px; }
        .result-item { display: flex; justify-content: space-between; align-items: center; margin: 12px 0; padding-bottom: 12px; border-bottom: 1px solid rgba(0,0,0,0.1); }
        .result-item:last-child { border-bottom: none; margin-bottom: 0; }
        .result-label { font-size: 14px; color: #333; font-weight: 600; }
        .result-value { font-size: 18px; font-weight: bold; color: #1565c0; text-align: right; }
        h3 { text-align: center; margin-top: 0; color: #1565c0; font-size: 16px; text-transform: uppercase; letter-spacing: 1px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="control-group">
            <label>📐 Площадь крыши (кв.м): <span class="val-display" id="areaVal">50</span></label>
            <input type="range" id="roofArea" min="10" max="200" value="50" step="5">
        </div>
        <div class="control-group">
            <label>☀️ Регион (инсоляция): <span class="val-display" id="regionVal">Краснодар</span></label>
            <select id="region">
                <option value="1150">Краснодарский край (1150 кВт·ч/кВт)</option>
                <option value="1100">Ростовская область (1100)</option>
                <option value="1150">Крым (1150)</option>
                <option value="850">Московская область (850)</option>
                <option value="900">Другой регион (900)</option>
            </select>
        </div>
        <div class="control-group">
            <label>💰 Ваш счет за свет (руб/мес): <span class="val-display" id="billVal">5000</span></label>
            <input type="range" id="monthlyBill" min="500" max="30000" value="5000" step="500">
        </div>
        <div class="control-group">
            <label>👤 Тип объекта (для расчета потребления): <span class="val-display" id="typeVal">Физлицо</span></label>
            <select id="clientType">
                <option value="6.5">Физлицо (средний тариф ~6.5 руб)</option>
                <option value="8.0">Бизнес (средний тариф ~8.0 руб)</option>
            </select>
        </div>
        
        <div class="results">
            <h3>⚡ Технические параметры системы:</h3>
            <div class="result-item">
                <span class="result-label">1. Какая мощность нужна?</span>
                <span class="result-value" id="powerResult">7.5 кВт</span>
            </div>
            <div class="result-item">
                <span class="result-label">2. Поместятся ли панели?</span>
                <span class="result-value" id="fitsResult">Да (на 50 м²)</span>
            </div>
            <div class="result-item">
                <span class="result-label">3. Чистая выработка в год:</span>
                <span class="result-value" id="productionResult">8 625 кВт·ч</span>
            </div>
        </div>
    </div>

    <script>
        const roofAreaInput = document.getElementById('roofArea');
        const monthlyBillInput = document.getElementById('monthlyBill');
        const regionSelect = document.getElementById('region');
        const typeSelect = document.getElementById('clientType');

        function updateDisplays() {
            document.getElementById('areaVal').textContent = roofAreaInput.value;
            document.getElementById('billVal').textContent = monthlyBillInput.value;
            document.getElementById('regionVal').textContent = regionSelect.options[regionSelect.selectedIndex].text.split('(')[0].trim();
            document.getElementById('typeVal').textContent = typeSelect.options[typeSelect.selectedIndex].text.split('(')[0].trim();
            calculate();
        }

        function calculate() {
            const area = parseFloat(roofAreaInput.value);
            const bill = parseFloat(monthlyBillInput.value);
            const insolation = parseFloat(regionSelect.value);
            const tariff = parseFloat(typeSelect.value);
            
            // 1. Считаем потребность по счету
            const monthlyConsumption = bill / tariff;
            const powerByConsumption = monthlyConsumption / 115.0; // 115 кВт·ч выработки с 1 кВт в месяц на Юге
            
            // 2. Считаем максимум по крыше (5.5 кв.м на 1 кВт)
            const powerByRoof = area / 5.5;
            
            // 3. Правило минимума: берем меньшее значение, округляем до 0.5, минимум 3 кВт
            const recommendedPower = Math.max(3.0, Math.min(powerByConsumption, powerByRoof));
            const roundedPower = Math.round(recommendedPower * 2) / 2; 
            
            const fits = roundedPower <= powerByRoof;
            const yearlyProduction = Math.round(roundedPower * insolation);
            
            // Вывод результатов
            document.getElementById('powerResult').textContent = roundedPower + ' кВт';
            document.getElementById('fitsResult').textContent = fits ? `✅ Да (на ${area} м²)` : `❌ Нет (макс. ${(area/5.5).toFixed(1)} кВт)`;
            document.getElementById('fitsResult').style.color = fits ? '#2e7d32' : '#c62828';
            document.getElementById('productionResult').textContent = yearlyProduction.toLocaleString('ru-RU') + ' кВт·ч';
        }

        // Слушатели событий для мгновенного пересчета
        roofAreaInput.addEventListener('input', updateDisplays);
        monthlyBillInput.addEventListener('input', updateDisplays);
        regionSelect.addEventListener('change', updateDisplays);
        typeSelect.addEventListener('change', updateDisplays);

        // Инициализация при загрузке
        updateDisplays();
    </script>
</body>
</html>
"""
