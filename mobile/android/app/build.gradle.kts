import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Upload keystore lives outside the repo at ~/.android-keys/keystore.properties.
// Falls back to debug signing when the file is absent (dev / CI without secrets).
// See docs/initial_specs/11_decisions/decision_log.md#d-057 for the keystore setup.
// CR267 WP-49 (prep): the Beta channel (scripts/lib/release_channel.sh) sets
// AMI_GRADLE_KEYSTORE_PROPERTIES / AMI_GRADLE_APPLICATION_ID to the company values.
// Unset (every Alpha build) they fall back to exactly the values used before.
val keystorePropertiesFile = file(
    System.getenv("AMI_GRADLE_KEYSTORE_PROPERTIES")
        ?: "${System.getProperty("user.home")}/.android-keys/keystore.properties"
)
val keystoreProperties = Properties().apply {
    if (keystorePropertiesFile.exists()) {
        keystorePropertiesFile.inputStream().use { load(it) }
    }
}
val hasUploadKeystore = keystoreProperties.getProperty("storeFile") != null

android {
    namespace = "ai.agenticmarketintel.ami_trade"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        applicationId = System.getenv("AMI_GRADLE_APPLICATION_ID") ?: "ai.agenticmarketintel.ami_trade"
        minSdk = 28
        // Play raises its target-API floor every year and enforces it on 31 August;
        // API 36 became mandatory 2026-08-31. Pinned rather than tracking
        // flutter.targetSdkVersion so the value matches what we test on. That pin is
        // why DEF396 happened - it went stale silently. Re-check before each August.
        targetSdk = 36
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasUploadKeystore) {
            create("release") {
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (hasUploadKeystore) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
        }
    }
}

flutter {
    source = "../.."
}
