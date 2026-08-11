package com.monday.colibri.network

import com.google.gson.GsonBuilder
import com.monday.colibri.data.*
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import java.util.concurrent.TimeUnit

/**
 * Retrofit API service for Monday Android Gateway.
 */
interface MondayApiService {
    
    @POST("register")
    suspend fun registerDevice(@Body request: DeviceRegisterRequest): Response<DeviceRegisterResponse>
    
    @POST("pair/{pairingCode}")
    suspend fun confirmPairing(@Path("pairingCode") pairingCode: String): Response<PairingConfirmResponse>
    
    @POST("actions")
    suspend fun submitAction(@Body action: ActionRequest): Response<ActionResponse>
    
    @GET("actions/{actionId}")
    suspend fun getActionStatus(@Path("actionId") actionId: String): Response<ActionResponse>
    
    @POST("permissions/{actionId}")
    suspend fun respondToPermission(
        @Path("actionId") actionId: String,
        @Body response: PermissionResponse
    ): Response<Map<String, String>>
    
    @GET("audit")
    suspend fun getAuditLog(@Query("limit") limit: Int = 50): Response<List<AuditLogEntry>>
    
    @GET("health")
    suspend fun healthCheck(): Response<Map<String, Any>>
}

object ApiClient {
    
    private const val DEFAULT_BASE_URL = "http://10.0.2.2:8765" // Android emulator localhost
    
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }
    
    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()
    
    private val gson = GsonBuilder()
        .setLenient()
        .create()
    
    private var retrofit: Retrofit? = null
    
    fun getInstance(baseUrl: String = DEFAULT_BASE_URL, authToken: String? = null): MondayApiService {
        val client = if (authToken != null) {
            okHttpClient.newBuilder()
                .addInterceptor { chain ->
                    val request = chain.request().newBuilder()
                        .addHeader("Authorization", "Bearer $authToken")
                        .build()
                    chain.proceed(request)
                }
                .build()
        } else {
            okHttpClient
        }
        
        retrofit = Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
        
        return retrofit!!.create(MondayApiService::class.java)
    }
}
