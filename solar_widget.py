# solar_widget.py

SOLAR_CALCULATOR_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Солнечный калькулятор</title>
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --text-color: #c9d1d9;
            --text-main: #ffffff;
            --accent-color: #58a6ff;
            --slider-thumb: #2f81f7;
            --sun-color: #ffc72c;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 10px;
        }

        .calculator-container {
            max-width: 800px;
            margin: 0 auto;
            background: var(--bg-color);
            border-radius: 8px;
            overflow: hidden;
        }

        /* Визуализационный экран */
        .visual-screen {
            position: relative;
            width: 100%;
            height: 380px;
            background: linear-gradient(to bottom, #07090e 0%, #0d1117 100%);
            border-radius: 8px 8px 0 0;
            overflow: hidden;
        }

        /* Метрики */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            background: #ffffff;
            color: #333333;
            padding: 20px 10px;
            text-align: center;
            border-bottom: 1px solid #e1e4e8;
        }

        .metric-item .label {
            font-size: 14px;
            color: #586069;
            margin-bottom: 5px;
        }

        .metric-item .value {
            font-size: 20px;
            font-weight: bold;
            color: #000000;
        }

        /* Панель управления */
        .controls-panel {
            padding: 25px 20px;
            background: var(--bg-color);
        }

        .control-group {
            margin-bottom: 25px;
        }

        .control-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .control-title {
            font-size: 16px;
            font-weight: 500;
            color: var(--text-main);
        }

        .control-value {
            font-size: 18px;
            font-weight: bold;
            color: var(--text-main);
        }

        .flex-row {
            display: flex;
            gap: 20px;
            align-items: center;
        }

        .flex-child {
            flex: 1;
        }

        /* Кастомизация слайдеров */
        input[type=range] {
            -webkit-appearance: none;
            width: 100%;
            background: #21262d;
            height: 6px;
            border-radius: 3px;
            outline: none;
        }

        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none;
            height: 18px;
            width: 18px;
            border-radius: 50%;
            background: var(--slider-thumb);
            cursor: pointer;
            transition: transform 0.1s;
        }

        input[type=range]::-webkit-slider-thumb:hover {
            transform: scale(1.2);
        }

        /* Выпадающий список */
        select {
            width: 100%;
            padding: 10px;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: var(--text-main);
            font-size: 16px;
            outline: none;
            cursor: pointer;
        }

        /* Подписи на SVG */
        .svg-label {
            font-size: 12px;
            fill: #ffffff;
            font-weight: 500;
            font-family: sans-serif;
        }
    </style>
</head>
<body>

<div class="calculator-container">
    <!-- Блок SVG визуализации -->
    <div class="visual-screen">
        <svg id="solar-svg" width="100%" height="100%" viewBox="0 0 800 380" xmlns="http://w3.org">
            <!-- Задний план и лучи солнца -->
            <defs>
                <radialGradient id="sun-glow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stop-color="#ffc72c" stop-opacity="1"/>
                    <stop offset="30%" stop-color="#ffc72c" stop-opacity="0.3"/>
                    <stop offset="100%" stop-color="#ffc72c" stop-opacity="0"/>
                </radialGradient>
                <linearGradient id="light-beam" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#ffc72c" stop-opacity="0.25"/>
                    <stop offset="100%" stop-color="#ffc72c" stop-opacity="0.0"/>
                </linearGradient>
            </defs>

            <!-- Солнце слева вверху -->
            <circle cx="150" cy="80" r="45" fill="url(#sun-glow)" />
            <circle cx="150" cy="80" r="20" fill="var(--sun-color)" />
            <text x="150" y="145" class="svg-label" text-anchor="middle">Солнце (Краснодар)</text>

            <!-- Световой конус, падающий прямо на лицевую сторону панели -->
            <polygon id="sun-ray" points="150,80 505,105 400,165" fill="url(#light-beam)" />

            <!-- Дом с правильным правым скатом под углом -->
            <!-- Задняя стена/основа дома -->
            <polygon points="400,240 660,240 660,165 400,165" fill="#1b212c" />
            <!-- Фронтон (треугольник крыши) -->
            <polygon points="400,165 660,165 530,95" fill="#222a36" />
            <!-- Окна дома -->
            <rect x="440" y="185" width="35" height="35" fill="#2d3748" rx="2"/>
            <rect x="585" y="185" width="35" height="35" fill="#2d3748" rx="2"/>

            <!-- Линия земли -->
            <line x1="50" y1="240" x2="750" y2="240" stroke="#1f242c" stroke-width="2" />

            <!-- Путь лучей (пунктир солнца к панели) -->
            <line x1="150" y1="80" x2="465" y2="130" stroke="#ffc72c" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.6" />

            <!-- Солнечная панель, лежащая на ЛЕВОМ скате (повернута К солнцу лицевой стороной) -->
            <!-- Скат идет от конька (530,95) вниз влево к углу стены (400,165) -->
            <line id="roof-line" x1="530" y1="95" x2="400" y2="165" stroke="#2d3748" stroke-width="4" />
            
            <!-- Динамическая синяя лицевая панель -->
            <line id="solar-panel" x1="520" y1="100" x2="410" y2="160" stroke="#0052cc" stroke-width="8" stroke-linecap="round" />
            <!-- Блик/текстура на лицевой стороне панели -->
            <line id="solar-panel-glare" x1="518" y1="99" x2="412" y2="159" stroke="#4c9aff" stroke-width="2" stroke-linecap="round" />

            <text id="panel-tag" x="480" y="80" class="svg-label" text-anchor="middle">Панели (45.0 м²)</text>

            <!-- Инвертор на стене внутри или снаружи дома -->
            <g transform="translate(320, 160)">
                <rect x="0" y="0" width="50" height="70" rx="8" fill="#28303d" stroke="#444c56" stroke-width="2"/>
                <rect x="8" y="8" width="34" height="20" rx="3" fill="#1c2128"/>
                <!-- Индикаторы инвертора -->
                <circle cx="15" cy="45" r="3" fill="#2ea44f" />
                <circle cx="25" cy="45" r="3" fill="#2ea44f" />
                <circle cx="35" cy="45" r="3" fill="#2ea44f" opacity="0.4" />
                <text x="25" y="62" font-size="9" fill="#8b949e" font-family="sans-serif" text-anchor="middle">Инвертор</text>
            </g>
            
            <!-- Пунктир связи панели с инвертором -->
            <path d="M 430,150 L 345,160" stroke="#2ea44f" stroke-width="1.5" stroke-dasharray="3,3" fill="none" opacity="0.7"/>
        </svg>
    </div>

    <!-- Блок отображения результатов -->
    <div class="metrics-grid">
        <div class="metric-item">
            <div class="label">Мощность СЭС</div>
            <div class="value" id="res-power">9.45 кВт</div>
        </div>
        <div class="metric-item">
            <div class="label">Выработка в год</div>
            <div class="value" id="res-generation">10 461 кВт·ч</div>
        </div>
        <div class="metric-item">
            <div class="label">Полезная площадь</div>
            <div class="value" id="res-area">45.0 м²</div>
        </div>
    </div>

    <!-- Интерфейс управления со слайдерами -->
    <div class="controls-panel">
        <!-- Слайдер 1: Общая площадь крыши -->
        <div class="control-group">
            <div class="control-header">
                <div class="control-title">Общая площадь крыши</div>
                <div class="control-value"><span id="val-roof-area">50</span> м²</div>
            </div>
            <input type="range" id="input-roof-area" min="10" max="200" value="50" step="5">
        </div>

        <!-- Слайдер 2 и Селект на одной строке -->
        <div class="flex-row">
            <!-- Угол наклона -->
            <div class="control-group flex-child">
                <div class="control-header">
                    <div class="control-title">Угол наклона ската</div>
                    <div class="control-value"><span id="val-tilt">35</span>°</div>
                </div>
                <input type="range" id="input-tilt" min="15" max="60" value="35" step="5">
            </div>

            <!-- Ориентация -->
            <div class="control-group flex-child">
                <div class="control-header">
                    <div class="control-title">Ориентация ската крыши</div>
                </div>
                <select id="input-orientation">
                    <option value="1.0" selected>Юг</option>
                    <option value="0.85">Юго-Восток / Юго-Запад</option>
                    <option value="0.70">Восток / Запад</option>
                    <option value="0.50">Север (не рекомендуется)</option>
                </select>
            </div>
        </div>
    </div>
</div>

<script>
