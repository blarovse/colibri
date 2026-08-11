package com.monday.colibri.data

import com.google.gson.annotations.SerializedName

data class DeviceRegisterRequest(
    @SerializedName("device_name") val deviceName: String,
    @SerializedName("device_public_key") val devicePublicKey: String,
    @SerializedName("device_model") val deviceModel: String? = null,
    @SerializedName("android_version") val androidVersion: String? = null,
    @SerializedName("app_version") val appVersion: String? = null
)

data class DeviceRegisterResponse(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("device_name") val deviceName: String,
    val token: String,
    @SerializedName("expires_at") val expiresAt: String,
    @SerializedName("pairing_code") val pairingCode: String
)

data class ActionRequest(
    @SerializedName("action_type") val actionType: String,
    val target: String,
    val parameters: Map<String, Any> = emptyMap(),
    @SerializedName("risk_level") val riskLevel: String = "LOW",
    @SerializedName("requires_confirmation") val requiresConfirmation: Boolean = false,
    @SerializedName("confirmation_prompt") val confirmationPrompt: String? = null,
    @SerializedName("task_id") val taskId: String? = null
)

data class ActionResponse(
    @SerializedName("action_id") val actionId: String,
    val status: String,
    val result: Map<String, Any>? = null,
    val error: String? = null
)

data class PermissionResponse(
    @SerializedName("action_id") val actionId: String,
    val approved: Boolean,
    val reason: String? = null
)

data class AuditLogEntry(
    @SerializedName("log_id") val logId: String,
    val timestamp: String,
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("action_type") val actionType: String,
    val target: String,
    val status: String,
    @SerializedName("risk_level") val riskLevel: String,
    @SerializedName("task_id") val taskId: String? = null
)

data class PairingConfirmResponse(
    val status: String,
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("device_name") val deviceName: String
)
