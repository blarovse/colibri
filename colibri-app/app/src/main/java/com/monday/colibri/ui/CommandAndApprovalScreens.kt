package com.monday.colibri.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CommandScreen(
    onSendCommand: (String, String, Map<String, Any>) -> Unit,
    onBack: () -> Unit
) {
    var selectedActionType by remember { mutableStateOf("VOICE_INPUT") }
    var targetInput by remember { mutableStateOf("") }
    var commandText by remember { mutableStateOf("") }
    
    val actionTypes = listOf(
        "VOICE_INPUT",
        "OPEN_APP",
        "SEARCH_WEB",
        "CREATE_PROJECT",
        "CHECK_STATUS"
    )
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Send Command") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp)
        ) {
            // Action type selector
            Text(
                text = "Action Type",
                style = MaterialTheme.typography.titleMedium
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            ExposedDropdownMenuBox(
                expanded = false,
                onExpandedChange = {}
            ) {
                OutlinedTextField(
                    value = selectedActionType,
                    onValueChange = { selectedActionType = it },
                    modifier = Modifier
                        .menuAnchor()
                        .fillMaxWidth(),
                    readOnly = true,
                    trailingIcon = { Icon(Icons.Default.ArrowDropDown, contentDescription = null) }
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Target input
            Text(
                text = "Target",
                style = MaterialTheme.typography.titleMedium
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            OutlinedTextField(
                value = targetInput,
                onValueChange = { targetInput = it },
                label = { Text("e.g., Chrome, Monday Assistant") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Command text
            Text(
                text = "Command / Voice Input",
                style = MaterialTheme.typography.titleMedium
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            OutlinedTextField(
                value = commandText,
                onValueChange = { commandText = it },
                label = { Text("Speak or type your command") },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(120.dp),
                placeholder = { Text("e.g., Create an expense tracker app") }
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Quick actions
            Text(
                text = "Quick Actions",
                style = MaterialTheme.typography.titleMedium
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FilterChip(
                    onClick = { commandText = "What's the status of my projects?" },
                    label = { Text("Status") },
                    selected = false,
                    leadingIcon = { Icon(Icons.Default.Info, contentDescription = null) }
                )
                
                FilterChip(
                    onClick = { commandText = "Create a new Android app" },
                    label = { Text("New App") },
                    selected = false,
                    leadingIcon = { Icon(Icons.Default.Add, contentDescription = null) }
                )
                
                FilterChip(
                    onClick = { commandText = "Open Chrome and search for Kotlin tutorials" },
                    label = { Text("Search") },
                    selected = false,
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) }
                )
            }
            
            Spacer(modifier = Modifier.weight(1f))
            
            // Send button
            Button(
                onClick = {
                    val params = mapOf("text" to commandText)
                    onSendCommand(selectedActionType, targetInput.ifEmpty { "monday_assistant" }, params)
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = commandText.isNotBlank()
            ) {
                Icon(Icons.Default.Send, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Send Command")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalScreen(
    onApprove: (String) -> Unit,
    onDeny: (String) -> Unit,
    onBack: () -> Unit
) {
    // Mock pending approvals - in production, fetch from API/WebSocket
    val pendingApprovals = remember {
        listOf(
            PendingApproval(
                actionId = "action_001",
                actionType = "OPEN_BROWSER",
                description = "Open Chrome and navigate to Instagram",
                riskLevel = "LOW"
            ),
            PendingApproval(
                actionId = "action_002",
                actionType = "POST_SOCIAL",
                description = "Publish post to Instagram with image and caption",
                riskLevel = "MEDIUM"
            )
        )
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pending Approvals") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        if (pendingApprovals.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        imageVector = Icons.Default.CheckCircleOutline,
                        contentDescription = null,
                        modifier = Modifier.size(64.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "No pending approvals",
                        style = MaterialTheme.typography.titleMedium
                    )
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(pendingApprovals.size) { index ->
                    val approval = pendingApprovals[index]
                    ApprovalCard(
                        approval = approval,
                        onApprove = { onApprove(approval.actionId) },
                        onDeny = { onDeny(approval.actionId) }
                    )
                }
            }
        }
    }
}

data class PendingApproval(
    val actionId: String,
    val actionType: String,
    val description: String,
    val riskLevel: String
)

@Composable
fun ApprovalCard(
    approval: PendingApproval,
    onApprove: () -> Unit,
    onDeny: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = approval.actionType,
                    style = MaterialTheme.typography.titleMedium
                )
                
                AssistChip(
                    onClick = { },
                    label = {
                        Text(
                            text = approval.riskLevel,
                            style = MaterialTheme.typography.labelSmall
                        )
                    },
                    colors = AssistChipDefaults.assistChipColors(
                        containerColor = when (approval.riskLevel) {
                            "LOW" -> MaterialTheme.colorScheme.secondaryContainer
                            "MEDIUM" -> MaterialTheme.colorScheme.tertiaryContainer
                            "HIGH" -> MaterialTheme.colorScheme.errorContainer
                            else -> MaterialTheme.colorScheme.surfaceVariant
                        }
                    )
                )
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = approval.description,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End
            ) {
                TextButton(onClick = onDeny) {
                    Icon(Icons.Default.Close, contentDescription = null)
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Deny")
                }
                
                Spacer(modifier = Modifier.width(8.dp))
                
                Button(onClick = onApprove) {
                    Icon(Icons.Default.Check, contentDescription = null)
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Approve")
                }
            }
        }
    }
}
