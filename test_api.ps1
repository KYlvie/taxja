# Step 1: Login and save token
$login = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/auth/login" -Method POST -Body '{"email":"fenghong.zhang@hotmail.com","password":"ZFHzfh920922"}' -ContentType "application/json" -UseBasicParsing
$token = ($login.Content | ConvertFrom-Json).access_token

# Step 2: List documents
$docs = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/documents/" -Method GET -Headers @{"Authorization"="Bearer $token"} -UseBasicParsing
$docList = $docs.Content | ConvertFrom-Json
Write-Host "=== Documents ==="
foreach ($d in $docList) {
    $sug = $d.ocr_result.import_suggestion
    if ($sug) {
        Write-Host "Doc $($d.id): type=$($d.document_type) sug_status=$($sug.status) sug_type=$($sug.type)"
    }
}

# Step 3: Check properties
Write-Host "`n=== Properties ==="
$props = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/properties/" -Method GET -Headers @{"Authorization"="Bearer $token"} -UseBasicParsing
$propList = $props.Content | ConvertFrom-Json
foreach ($p in $propList) {
    Write-Host "Property $($p.id): addr=$($p.address) price=$($p.purchase_price) rental=$($p.rental_percentage)%"
}

# Step 4: Check recurring transactions
Write-Host "`n=== Recurring ==="
$rec = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/recurring/" -Method GET -Headers @{"Authorization"="Bearer $token"} -UseBasicParsing
$recList = $rec.Content | ConvertFrom-Json
foreach ($r in $recList) {
    Write-Host "Recurring $($r.id): desc=$($r.description) amount=$($r.amount) property=$($r.property_id)"
}
