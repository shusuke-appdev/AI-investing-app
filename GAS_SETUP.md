# Google Apps Script Setup Guide (Update)

この手順は、**既存のポートフォリオ用GASプロジェクトを更新**し、参照知識の保存機能を追加するためのものです。
既存のポートフォリオデータは保持されます（スプレッドシートのデータは消えません）。

## ⚠️ 重要: 更新手順

1.  **既存のGASプロジェクトを開く**
    - ポートフォリオ管理に使っているGoogleスプレッドシートを開き、`拡張機能` > `Apps Script` をクリックします。

2.  **コードの上書き**
    - エディタに表示されている**古いコードをすべて削除**してください。
    - 下記の「New Google Apps Script Code」をすべてコピーして貼り付けてください。
    - `Ctrl + S` (Macは `Cmd + S`) で保存します。

3.  **新しいデプロイ (必須)**
    - 右上の `デプロイ` > `デプロイを管理` を選択。
    - **鉛筆アイコン** (編集) をクリック。
    - **バージョン**: `新バージョン` (New version) を選択。
    - `デプロイ` ボタンをクリック。
    - ※ URLは変わりませんが、バージョンを更新しないと新しいコードが反映されません。

4.  **完了**
    - アプリ側での設定変更は不要です（URLが変わっていない場合）。
    - アプリで参照知識を保存・削除してみて、動作を確認してください。

---

## New Google Apps Script Code

```javascript
// ==========================================
// AI Investing App Backend Script (v2: Knowledge Base Added)
// ==========================================

function doGet(e) {
  var params = e.parameter;
  var action = params.action;
  
  if (action == "list") {
    return listPortfolios();
  } else if (action == "load") {
    return loadPortfolio(params.name);
  } else if (action == "history") {
    return getHistory(params.name, params.days);
  } else if (action == "alerts") {
    return getAlerts(params.name);
  } else if (action == "get_knowledge") {
    return getKnowledge();
  }
  
  return jsonResponse({error: "Invalid action"});
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var action = data.action;
    
    if (action == "save") {
      return savePortfolio(data.name, data.holdings);
    } else if (action == "delete") {
      return deletePortfolio(data.name);
    } else if (action == "save_snapshot") {
      return saveSnapshot(data.name, data.total_value, data.holdings);
    } else if (action == "set_alert") {
      return setAlert(data.portfolio_name, data.email, data.alert_type, data.threshold);
    } else if (action == "delete_alert") {
      return deleteAlert(data.portfolio_name, data.alert_type);
    } else if (action == "send_alert") {
      return sendEmail(data.email, data.subject, data.body);
    } else if (action == "save_knowledge") {
      return saveKnowledge(data.item);
    } else if (action == "delete_knowledge") {
      return deleteKnowledge(data.id);
    }
    
    return jsonResponse({error: "Invalid action"});
  } catch (err) {
    return jsonResponse({error: err.toString()});
  }
}

// ------------------------------------------
// Knowledge Base Functions (NEW)
// ------------------------------------------

function getKnowledge() {
  var sheet = getOrCreateSheet("Knowledge");
  var data = sheet.getDataRange().getValues();
  var items = [];
  
  // Skip header (row 1)
  for (var i = 1; i < data.length; i++) {
    var jsonStr = data[i][5]; // 'json_data' column
    if (jsonStr) {
      try {
        items.push(JSON.parse(jsonStr));
      } catch (e) {
        // ignore invalid json
      }
    }
  }
  
  return jsonResponse({items: items});
}

function saveKnowledge(item) {
  var sheet = getOrCreateSheet("Knowledge");
  // Ensure header
  if (sheet.getLastRow() == 0) {
    sheet.appendRow(["id", "title", "source_type", "summary", "created_at", "json_data"]);
  }
  
  var id = item.id;
  var data = sheet.getDataRange().getValues();
  var rowIndex = -1;
  
  // Find existing
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] == id) {
      rowIndex = i + 1; // 1-based index
      break;
    }
  }
  
  var rowData = [
    item.id,
    item.title,
    item.source_type,
    item.summary,
    item.created_at,
    JSON.stringify(item)
  ];
  
  if (rowIndex > 0) {
    // Update
    sheet.getRange(rowIndex, 1, 1, 6).setValues([rowData]);
  } else {
    // Append
    sheet.appendRow(rowData);
  }
  
  return jsonResponse({success: true});
}

function deleteKnowledge(id) {
  var sheet = getOrCreateSheet("Knowledge");
  var data = sheet.getDataRange().getValues();
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] == id) {
      sheet.deleteRow(i + 1);
      return jsonResponse({success: true});
    }
  }
  return jsonResponse({success: false}); // Not found is strictly not a success but harmless
}

// ------------------------------------------
// Portfolio Functions
// ------------------------------------------

function listPortfolios() {
  var sheet = getOrCreateSheet("Portfolios");
  var data = sheet.getDataRange().getValues();
  var names = [];
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0]) names.push(data[i][0]);
  }
  
  return jsonResponse({portfolios: names});
}

function loadPortfolio(name) {
  var sheet = getOrCreateSheet("Portfolios");
  var data = sheet.getDataRange().getValues();
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] == name) {
      var holdingsJson = data[i][1];
      return jsonResponse({
        name: name,
        holdings: JSON.parse(holdingsJson),
        updated_at: data[i][2]
      });
    }
  }
  return jsonResponse({error: "Not found"});
}

function savePortfolio(name, holdings) {
  var sheet = getOrCreateSheet("Portfolios");
  if (sheet.getLastRow() == 0) {
    sheet.appendRow(["name", "holdings", "updated_at"]);
  }
  
  var data = sheet.getDataRange().getValues();
  var rowIndex = -1;
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] == name) {
      rowIndex = i + 1;
      break;
    }
  }
  
  var now = new Date().toISOString();
  var rowData = [name, JSON.stringify(holdings), now];
  
  if (rowIndex > 0) {
    sheet.getRange(rowIndex, 1, 1, 3).setValues([rowData]);
  } else {
    sheet.appendRow(rowData);
  }
  
  return jsonResponse({success: true});
}

function deletePortfolio(name) {
  var sheet = getOrCreateSheet("Portfolios");
  var data = sheet.getDataRange().getValues();
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] == name) {
      sheet.deleteRow(i + 1);
      return jsonResponse({success: true});
    }
  }
  return jsonResponse({success: false});
}

// ------------------------------------------
// History Functions
// ------------------------------------------

function saveSnapshot(name, totalValue, holdings) {
  var sheet = getOrCreateSheet("History");
  if (sheet.getLastRow() == 0) {
    sheet.appendRow(["timestamp", "name", "total_value", "holdings"]);
  }
  
  var now = new Date().toISOString();
  sheet.appendRow([now, name, totalValue, JSON.stringify(holdings)]);
  
  return jsonResponse({success: true});
}

function getHistory(name, days) {
  var sheet = getOrCreateSheet("History");
  var data = sheet.getDataRange().getValues();
  var history = [];
  var cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - parseInt(days || 30));
  
  for (var i = 1; i < data.length; i++) {
    var ts = new Date(data[i][0]);
    if (data[i][1] == name && ts >= cutoff) {
      history.push({
        timestamp: data[i][0],
        total_value: data[i][2],
        holdings: JSON.parse(data[i][3])
      });
    }
  }
  
  return jsonResponse({history: history});
}

// ------------------------------------------
// Alert Functions
// ------------------------------------------

function setAlert(portfolioName, email, alertType, threshold) {
  var sheet = getOrCreateSheet("Alerts");
  if (sheet.getLastRow() == 0) {
    sheet.appendRow(["portfolio_name", "email", "alert_type", "threshold", "created_at"]);
  }
  
  // 重複チェック＆削除（同じ条件なら上書き）
  deleteAlert(portfolioName, alertType);
  
  var now = new Date().toISOString();
  sheet.appendRow([portfolioName, email, alertType, threshold, now]);
  
  return jsonResponse({success: true});
}

function deleteAlert(portfolioName, alertType) {
  var sheet = getOrCreateSheet("Alerts");
  var data = sheet.getDataRange().getValues();
  
  // 後ろから削除（行ずれ防止）
  for (var i = data.length - 1; i >= 1; i--) {
    if (data[i][0] == portfolioName && data[i][2] == alertType) {
      sheet.deleteRow(i + 1);
    }
  }
  return jsonResponse({success: true});
}

function getAlerts(portfolioName) {
  var sheet = getOrCreateSheet("Alerts");
  var data = sheet.getDataRange().getValues();
  var alerts = [];
  
  for (var i = 1; i < data.length; i++) {
    if (!portfolioName || data[i][0] == portfolioName) {
      alerts.push({
        portfolio_name: data[i][0],
        email: data[i][1],
        alert_type: data[i][2],
        threshold: data[i][3]
      });
    }
  }
  return jsonResponse({alerts: alerts});
}

function sendEmail(email, subject, body) {
  MailApp.sendEmail({
    to: email,
    subject: subject,
    body: body
  });
  return jsonResponse({success: true});
}

// ------------------------------------------
// Helpers
// ------------------------------------------

function getOrCreateSheet(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  }
  return sheet;
}

function jsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
```
