plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.openmodelgarage.tvlauncher"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.openmodelgarage.tvlauncher"
        minSdk = 21          // revisit after the TV inventory (its SDK level)
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            signingConfig = signingConfigs.getByName("debug") // personal sideload; no store upload
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
// No dependencies on purpose: framework views only (small APK, fast cold start).
