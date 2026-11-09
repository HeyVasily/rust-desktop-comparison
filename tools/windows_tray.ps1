# Find a notification-area button by tooltip text through UI Automation and, with
# -Invoke, press it. Prints one JSON object: what was searched and what was found.
param([string]$Name = 'Veranda shell check', [switch]$Invoke)

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [Windows.Automation.AutomationElement]::RootElement
$report = [ordered]@{ containers = @(); matches = @(); names = @() }
foreach ($class in 'Shell_TrayWnd', 'NotifyIconOverflowWindow') {
    $condition = New-Object Windows.Automation.PropertyCondition(
        [Windows.Automation.AutomationElement]::ClassNameProperty, $class)
    $container = $root.FindFirst([Windows.Automation.TreeScope]::Children, $condition)
    $report.containers += [ordered]@{ class = $class; found = [bool]$container }
    if (-not $container) { continue }
    $elements = $container.FindAll([Windows.Automation.TreeScope]::Descendants,
        [Windows.Automation.Condition]::TrueCondition)
    foreach ($element in $elements) {
        $label = $element.Current.Name
        if (-not $label) { continue }
        $report.names += "$class/$label"
        if ($label -notlike "*$Name*") { continue }
        $match = [ordered]@{
            container = $class
            name = $label
            control = $element.Current.ControlType.ProgrammaticName
            rectangle = "$($element.Current.BoundingRectangle)"
        }
        if ($Invoke) {
            try {
                $element.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
                $match.invoked = $true
            } catch {
                $match.invoke_error = "$_"
            }
        }
        $report.matches += $match
    }
}
$report | ConvertTo-Json -Compress -Depth 4
