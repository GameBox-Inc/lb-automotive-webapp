# Search all PDFs for a specific term
# Usage: .\search_all_pdfs.ps1 -SearchTerm "kubernetes"

param(
    [Parameter(Mandatory = $true)]
    [string]$SearchTerm,
    
    [string]$PDFPath = "C:\Users\Terry\iCloudDrive\Tech Books"
)

Write-Host "🔍 Searching for: '$SearchTerm' in all PDFs" -ForegroundColor Green
Write-Host "📂 Path: $PDFPath" -ForegroundColor Cyan
Write-Host ""

$pdfs = Get-ChildItem -Path $PDFPath -Recurse -Filter *.pdf

if ($pdfs.Count -eq 0) {
    Write-Host "❌ No PDF files found in $PDFPath" -ForegroundColor Red
    exit 1
}

Write-Host "📚 Found $($pdfs.Count) PDF files" -ForegroundColor Yellow
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$extractScript = Join-Path $scriptDir "extract_pdf.py"

if (-not (Test-Path $extractScript)) {
    Write-Host "❌ extract_pdf.py not found at: $extractScript" -ForegroundColor Red
    exit 1
}

$foundMatches = $false

foreach ($pdf in $pdfs) {
    Write-Host "📖 Searching: $($pdf.Name)" -ForegroundColor Cyan
    
    try {
        $output = python $extractScript $pdf.FullName $null $SearchTerm 2>&1
        
        if ($output -match "Found \d+ matches") {
            $foundMatches = $true
            Write-Host $output -ForegroundColor Green
            Write-Host ""
        }
    }
    catch {
        Write-Host "  ⚠️  Error processing $($pdf.Name): $_" -ForegroundColor Yellow
    }
}

if (-not $foundMatches) {
    Write-Host "`n❌ Term '$SearchTerm' not found in any PDFs" -ForegroundColor Red
}
else {
    Write-Host "`n✅ Search complete!" -ForegroundColor Green
}
