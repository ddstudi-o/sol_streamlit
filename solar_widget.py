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
        .visual-screen {
            position: relative;
            width: 100%;
            height: 380px;
            background: linear-gradient(to bottom, #07090e 0%, #0d1117 100%);
            border-radius: 8px 8px 0 0;
            overflow: hidden;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            background: #ffffff;
            color: #333333;
            padding: 20px 10px;
            text-align: center;
            border-bottom: 1px solid #e1e4e8;
        }
        .metric-item .label { font-size: 14px; color: #586069; margin-bottom: 5px; }
        .metric-item .value { font-size: 20px; font-weight: bold; color: #000000; }
        .controls-panel { padding: 25px 20px; background: var(--bg-color); }
        .control-group { margin-bottom: 25px; }
        .control-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .control-title { font-size: 16px; font-weight: 500; color: var(--text-main); }
        .control-value { font-size: 18px; font-weight: bold; color: var(--text-main); }
        .flex-row { display: flex; gap: 20px; align-items: center; }
        .flex-child { flex: 1; }
        input[type=range] {
            -webkit-appearance: none; width: 100%; background: #21262d; height: 6px; border-radius: 3px; outline: none;
        }
        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none; height: 18px; width: 18px; border-radius: 50%; background: var(--slider-thumb); cursor: pointer; transition: transform 0.1s;
        }
        input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.2); }
        select {
            width: 100%; padding: 10px; background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: var(--text-main); font-size: 16px; outline: none; cursor: pointer;
        }
        .svg-label { font-size: 12px; fill: #ffffff; font-weight: 500; font-family: sans-serif; }
    </style>
</head>
<body>

<div class="calculator-container">
    <div class="visual-screen">
        <svg id="solar-svg" width="100%" height="100%" viewBox="0 0 800 380" xmlns="http://www.w3.org/2000/svg">
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

            <circle cx="150" cy="80" r="45" fill="url(#sun-glow)" />
            <circle cx="150" cy="80" r="20" fill="var(--sun-color)" />
            <text x="150" y="145" class="svg-label" text-anchor="middle">Солнце (Краснодар)</text>

            <polygon id="sun-ray" points="150,80 505,105 400,165" fill="url(#light-beam)" />
            <polygon points="400,240 660,240 660,165 400,165" fill="#1b212c" />
            <polygon points="400,165 660,165 530,95" fill="#222a36" />
            <rect x="440" y="185" width="35" height="35" fill="#2d3748" rx="2"/>
            <rect x="585" y="185" width="35" height="35" fill="#2d3748" rx="2"/>
            <line x1="50" y1="240" x2="750" y2="240" stroke="#1f242c" stroke-width="2" />
            <line x1="150" y1="80" x2="465" y2="130" stroke="#ffc72c" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.6" />
            <line id="roof-line" x1="530" y1="95" x2="400" y2="165" stroke="#2d3748" stroke-width="4" />
            <line id="solar-panel" x1="520" y1="100" x2="410" y2="160" stroke="#0052cc" stroke-width="8" stroke-linecap="round" />
            <line id="solar-panel-glare" x1="518" y1="99" x2="412" y2="159" stroke="#4c9aff" stroke-width="2" stroke-linecap="round" />
            <text id="panel-tag" x="480" y="80" class="svg-label" text-anchor="middle">Панели (45.0 м²)</text>
            <g transform="translate(320, 160)">
                <rect x="0" y="0" width="50" height="70" rx="8" fill="#28303d" stroke="#444c56" stroke-width="2"/>
                <rect x="8" y="8" width="34" height="20" rx="3" fill="#1c2128"/>
                <circle cx="15" cy="45" r="3" fill="#2ea44f" />
                <circle cx="25" cy="45" r="3" fill="#2ea44f" />
                <circle cx="35" cy="45" r="3" fill="#2ea44f" opacity="0.4" />
                <text x="25" y="62" font-size="9" fill="#8b949e" font-family="sans-serif" text-anchor="middle">Инвертор</text>
            </g>
            <path d="M 430,150 L 345,160" stroke="#2ea44f" stroke-width="1.5" stroke-dasharray="3,3" fill="none" opacity="0.7"/>
        </svg>
    </div>

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

    <div class="controls-panel">
        <div class="control-group">
            <div class="control-header">
                <div class="control-title">Общая площадь крыши</div>
                <div class="control-value"><span id="val-roof-area">50</span> м²</div>
            </div>
            <input type="range" id="input-roof-area" min="10" max="200" value="50" step="5">
        </div>
        <div class="flex-row">
            <div class="control-group flex-child">
                <div class="control-header">
                    <div class="control-title">Угол наклона ската</div>
                    <div class="control-value"><span id="val-tilt">35</span>°</div>
                </div>
                <input type="range" id="input-tilt" min="15" max="60" value="35" step="5">
            </div>
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
    const INSOLATION_BASE = 1250;
    const SQM_PER_KW = 6.2;
    const ROOF_EFFICIENCY = 0.9;

    const inputRoofArea = document.getElementById('input-roof-area');
    const inputTilt = document.getElementById('input-tilt');
    const inputOrientation = document.getElementById('input-orientation');

    const txtRoofArea = document.getElementById('val-roof-area');
    const txtTilt = document.getElementById('val-tilt');
    const resPower = document.getElementById('res-power');
    const resGeneration = document.getElementById('res-generation');
    const resArea = document.getElementById('res-area');

    const svgPanel = document.getElementById('solar-panel');
    const svgPanelGlare = document.getElementById('solar-panel-glare');
    const svgPanelTag = document.getElementById('panel-tag');
    const svgSunRay = document.getElementById('sun-ray');

    function calculateSolarSystem() {
        const roofArea = parseFloat(inputRoofArea.value);
        const tiltAngle = parseInt(inputTilt.value);
        const orientationCoeff = parseFloat(inputOrientation.value);

        txtRoofArea.innerText = roofArea;
        txtTilt.innerText = tiltAngle;

        const usefulArea = roofArea * ROOF_EFFICIENCY;
        const systemPowerKw = usefulArea / SQM_PER_KW;

        let tiltCoeff = 1.0;
        const diffFromIdeal = Math.abs(tiltAngle - 35);
        tiltCoeff = 1.0 - (diffFromIdeal * 0.004);

        const annualGeneration = systemPowerKw * INSOLATION_BASE * tiltCoeff * orientationCoeff;

        resPower.innerText = systemPowerKw.toFixed(2) + ' кВт';
        resGeneration.innerText = Math.round(annualGeneration).toLocaleString('ru-RU') + ' кВт·ч';
        resArea.innerText = usefulArea.toFixed(1) + ' м²';

        const minArea = 10;
        const maxArea = 200;
        const normalizedSize = (roofArea - minArea) / (maxArea - minArea);
        const panelThickness = 4 + (normalizedSize * 10);
        
        svgPanel.setAttribute('stroke-width', panelThickness);
        svgPanelGlare.setAttribute('stroke-width', panelThickness / 3);
        
        // ИСПРАВЛЕНО: добавлены обратные кавычки для шаблонной строки JS
        svgPanelTag.textContent = `Панели (${usefulArea.toFixed(1)} м²)`;

        const totalEfficiency = tiltCoeff * orientationCoeff;
        svgSunRay.setAttribute('opacity', (0.1 + (totalEfficiency * 0.2)).toFixed(2));
    }

    inputRoofArea.addEventListener('input', calculateSolarSystem);
    inputTilt.addEventListener('input', calculateSolarSystem);
    inputOrientation.addEventListener('change', calculateSolarSystem);

    calculateSolarSystem();
</script>
</body>
</html>
"""
