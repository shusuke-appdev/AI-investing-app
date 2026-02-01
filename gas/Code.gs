/**
 * AI投資アプリ - GAS連携スクリプト
 * スプレッドシートをポートフォリオデータのストレージとして使用
 * 履歴保存・Gmailアラート機能付き
 * 
 * 使用方法:
 * 1. Google Driveで新しいスプレッドシートを作成
 * 2. ツール → スクリプトエディタ
 * 3. このコードを貼り付けて保存
 * 4. デプロイ → 新しいデプロイ → ウェブアプリ
 * 5. アクセス: 「全員」に設定
 * 6. デプロイ後のURLをアプリに設定
 */

// シート名
const PORTFOLIO_SHEET = "Portfolios";
const HOLDINGS_SHEET = "Holdings";
const HISTORY_SHEET = "History";
const ALERTS_SHEET = "Alerts";

/**
 * 初期設定 - シートがなければ作成
 */
function initSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // Portfoliosシート
  let portfolioSheet = ss.getSheetByName(PORTFOLIO_SHEET);
  if (!portfolioSheet) {
    portfolioSheet = ss.insertSheet(PORTFOLIO_SHEET);
    portfolioSheet.appendRow(["name", "created_at", "updated_at"]);
  }
  
  // Holdingsシート
  let holdingsSheet = ss.getSheetByName(HOLDINGS_SHEET);
  if (!holdingsSheet) {
    holdingsSheet = ss.insertSheet(HOLDINGS_SHEET);
    holdingsSheet.appendRow(["portfolio_name", "ticker", "shares", "avg_cost"]);
  }
  
  // Historyシート
  let historySheet = ss.getSheetByName(HISTORY_SHEET);
  if (!historySheet) {
    historySheet = ss.insertSheet(HISTORY_SHEET);
    historySheet.appendRow(["portfolio_name", "date", "total_value", "holdings_json"]);
  }
  
  // Alertsシート
  let alertsSheet = ss.getSheetByName(ALERTS_SHEET);
  if (!alertsSheet) {
    alertsSheet = ss.insertSheet(ALERTS_SHEET);
    alertsSheet.appendRow(["portfolio_name", "email", "alert_type", "threshold", "enabled", "last_triggered"]);
  }
}

/**
 * GET リクエスト処理
 */
function doGet(e) {
  initSheets();
  
  const action = e.parameter.action || "list";
  const name = e.parameter.name || "";
  
  let result;
  
  switch (action) {
    case "list":
      result = listPortfolios();
      break;
    case "load":
      result = loadPortfolio(name);
      break;
    case "history":
      result = getHistory(name, parseInt(e.parameter.days) || 30);
      break;
    case "alerts":
      result = getAlerts(name);
      break;
    default:
      result = { error: "Unknown action" };
  }
  
  return ContentService
    .createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * POST リクエスト処理
 */
function doPost(e) {
  initSheets();
  
  let data;
  try {
    data = JSON.parse(e.postData.contents);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: "Invalid JSON" }))
      .setMimeType(ContentService.MimeType.JSON);
  }
  
  const action = data.action || "";
  let result;
  
  switch (action) {
    case "save":
      result = savePortfolio(data.name, data.holdings);
      break;
    case "delete":
      result = deletePortfolio(data.name);
      break;
    case "save_snapshot":
      result = saveSnapshot(data.name, data.total_value, data.holdings);
      break;
    case "set_alert":
      result = setAlert(data.portfolio_name, data.email, data.alert_type, data.threshold);
      break;
    case "delete_alert":
      result = deleteAlert(data.portfolio_name, data.alert_type);
      break;
    case "send_alert":
      result = sendAlertEmail(data.email, data.subject, data.body);
      break;
    default:
      result = { error: "Unknown action" };
  }
  
  return ContentService
    .createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

// ============================================================
// ポートフォリオ管理
// ============================================================

function listPortfolios() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(PORTFOLIO_SHEET);
  const data = sheet.getDataRange().getValues();
  
  const portfolios = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i][0]) {
      portfolios.push(data[i][0]);
    }
  }
  
  return { portfolios: portfolios };
}

function loadPortfolio(name) {
  if (!name) {
    return { error: "Portfolio name required" };
  }
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  const portfolioSheet = ss.getSheetByName(PORTFOLIO_SHEET);
  const portfolioData = portfolioSheet.getDataRange().getValues();
  let portfolioInfo = null;
  
  for (let i = 1; i < portfolioData.length; i++) {
    if (portfolioData[i][0] === name) {
      portfolioInfo = {
        name: portfolioData[i][0],
        created_at: portfolioData[i][1],
        updated_at: portfolioData[i][2]
      };
      break;
    }
  }
  
  if (!portfolioInfo) {
    return { error: "Portfolio not found" };
  }
  
  const holdingsSheet = ss.getSheetByName(HOLDINGS_SHEET);
  const holdingsData = holdingsSheet.getDataRange().getValues();
  const holdings = [];
  
  for (let i = 1; i < holdingsData.length; i++) {
    if (holdingsData[i][0] === name) {
      holdings.push({
        ticker: holdingsData[i][1],
        shares: holdingsData[i][2],
        avg_cost: holdingsData[i][3] || null
      });
    }
  }
  
  return {
    name: portfolioInfo.name,
    created_at: portfolioInfo.created_at,
    updated_at: portfolioInfo.updated_at,
    holdings: holdings
  };
}

function savePortfolio(name, holdings) {
  if (!name || !holdings) {
    return { error: "Name and holdings required" };
  }
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const now = new Date().toISOString();
  
  deletePortfolioData(name);
  
  const portfolioSheet = ss.getSheetByName(PORTFOLIO_SHEET);
  portfolioSheet.appendRow([name, now, now]);
  
  const holdingsSheet = ss.getSheetByName(HOLDINGS_SHEET);
  for (const h of holdings) {
    holdingsSheet.appendRow([name, h.ticker, h.shares, h.avg_cost || ""]);
  }
  
  return { success: true, name: name };
}

function deletePortfolio(name) {
  if (!name) {
    return { error: "Portfolio name required" };
  }
  
  deletePortfolioData(name);
  return { success: true };
}

function deletePortfolioData(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  const portfolioSheet = ss.getSheetByName(PORTFOLIO_SHEET);
  const portfolioData = portfolioSheet.getDataRange().getValues();
  for (let i = portfolioData.length - 1; i >= 1; i--) {
    if (portfolioData[i][0] === name) {
      portfolioSheet.deleteRow(i + 1);
    }
  }
  
  const holdingsSheet = ss.getSheetByName(HOLDINGS_SHEET);
  const holdingsData = holdingsSheet.getDataRange().getValues();
  for (let i = holdingsData.length - 1; i >= 1; i--) {
    if (holdingsData[i][0] === name) {
      holdingsSheet.deleteRow(i + 1);
    }
  }
}

// ============================================================
// 履歴管理
// ============================================================

function saveSnapshot(portfolioName, totalValue, holdings) {
  if (!portfolioName) {
    return { error: "Portfolio name required" };
  }
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(HISTORY_SHEET);
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  
  // 同じ日のデータがあれば削除
  const data = sheet.getDataRange().getValues();
  for (let i = data.length - 1; i >= 1; i--) {
    if (data[i][0] === portfolioName && data[i][1] === today) {
      sheet.deleteRow(i + 1);
    }
  }
  
  // 新規追加
  sheet.appendRow([
    portfolioName,
    today,
    totalValue,
    JSON.stringify(holdings || [])
  ]);
  
  // アラートチェック
  checkAndTriggerAlerts(portfolioName, totalValue);
  
  return { success: true, date: today };
}

function getHistory(portfolioName, days) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(HISTORY_SHEET);
  const data = sheet.getDataRange().getValues();
  
  const history = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === portfolioName) {
      history.push({
        date: data[i][1],
        total_value: data[i][2],
        holdings: JSON.parse(data[i][3] || "[]")
      });
    }
  }
  
  // 日付でソートして最新N件
  history.sort((a, b) => a.date.localeCompare(b.date));
  return { history: history.slice(-days) };
}

// ============================================================
// アラート管理
// ============================================================

function setAlert(portfolioName, email, alertType, threshold) {
  if (!portfolioName || !email || !alertType) {
    return { error: "Portfolio name, email, and alert type required" };
  }
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(ALERTS_SHEET);
  
  // 既存アラートを削除
  const data = sheet.getDataRange().getValues();
  for (let i = data.length - 1; i >= 1; i--) {
    if (data[i][0] === portfolioName && data[i][2] === alertType) {
      sheet.deleteRow(i + 1);
    }
  }
  
  // 新規追加
  sheet.appendRow([portfolioName, email, alertType, threshold, true, ""]);
  
  return { success: true };
}

function deleteAlert(portfolioName, alertType) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(ALERTS_SHEET);
  const data = sheet.getDataRange().getValues();
  
  for (let i = data.length - 1; i >= 1; i--) {
    if (data[i][0] === portfolioName && data[i][2] === alertType) {
      sheet.deleteRow(i + 1);
    }
  }
  
  return { success: true };
}

function getAlerts(portfolioName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(ALERTS_SHEET);
  const data = sheet.getDataRange().getValues();
  
  const alerts = [];
  for (let i = 1; i < data.length; i++) {
    if (!portfolioName || data[i][0] === portfolioName) {
      alerts.push({
        portfolio_name: data[i][0],
        email: data[i][1],
        alert_type: data[i][2],
        threshold: data[i][3],
        enabled: data[i][4],
        last_triggered: data[i][5]
      });
    }
  }
  
  return { alerts: alerts };
}

function checkAndTriggerAlerts(portfolioName, currentValue) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const alertSheet = ss.getSheetByName(ALERTS_SHEET);
  const historySheet = ss.getSheetByName(HISTORY_SHEET);
  
  // 履歴から前日の値を取得
  const historyData = historySheet.getDataRange().getValues();
  let previousValue = null;
  
  const sortedHistory = historyData
    .filter((row, i) => i > 0 && row[0] === portfolioName)
    .sort((a, b) => b[1].localeCompare(a[1]));
  
  if (sortedHistory.length >= 2) {
    previousValue = sortedHistory[1][2]; // 前日の値
  }
  
  if (!previousValue) return;
  
  const changePercent = ((currentValue - previousValue) / previousValue) * 100;
  
  // アラートチェック
  const alertData = alertSheet.getDataRange().getValues();
  for (let i = 1; i < alertData.length; i++) {
    if (alertData[i][0] === portfolioName && alertData[i][4]) {
      const alertType = alertData[i][2];
      const threshold = alertData[i][3];
      const email = alertData[i][1];
      
      let shouldTrigger = false;
      let subject = "";
      let body = "";
      
      if (alertType === "daily_change" && Math.abs(changePercent) >= threshold) {
        shouldTrigger = true;
        subject = `[AI投資アプリ] ${portfolioName} - 日次変動アラート`;
        body = `ポートフォリオ「${portfolioName}」の評価額が${changePercent.toFixed(2)}%変動しました。\n\n` +
               `前日: $${previousValue.toLocaleString()}\n` +
               `現在: $${currentValue.toLocaleString()}\n` +
               `変動: ${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%`;
      }
      
      if (alertType === "value_below" && currentValue < threshold) {
        shouldTrigger = true;
        subject = `[AI投資アプリ] ${portfolioName} - 評価額下限アラート`;
        body = `ポートフォリオ「${portfolioName}」の評価額が設定下限を下回りました。\n\n` +
               `現在: $${currentValue.toLocaleString()}\n` +
               `設定下限: $${threshold.toLocaleString()}`;
      }
      
      if (alertType === "value_above" && currentValue > threshold) {
        shouldTrigger = true;
        subject = `[AI投資アプリ] ${portfolioName} - 評価額上限アラート`;
        body = `ポートフォリオ「${portfolioName}」の評価額が設定上限を超えました。\n\n` +
               `現在: $${currentValue.toLocaleString()}\n` +
               `設定上限: $${threshold.toLocaleString()}`;
      }
      
      if (shouldTrigger) {
        try {
          GmailApp.sendEmail(email, subject, body);
          // 最終トリガー日時を更新
          alertSheet.getRange(i + 1, 6).setValue(new Date().toISOString());
        } catch (e) {
          console.error("Failed to send alert email:", e);
        }
      }
    }
  }
}

/**
 * 直接メール送信
 */
function sendAlertEmail(email, subject, body) {
  if (!email || !subject || !body) {
    return { error: "Email, subject, and body required" };
  }
  
  try {
    GmailApp.sendEmail(email, subject, body);
    return { success: true };
  } catch (e) {
    return { error: "Failed to send email: " + e.message };
  }
}
