plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Firebase Crashlytics : activé seulement si android/app/google-services.json est présent.
// Ce fichier n'est PAS dans le dépôt public (.gitignore) : les builds sans lui (CI, contributeurs)
// fonctionnent normalement, simplement sans remontée des plantages.
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
    apply(plugin = "com.google.firebase.crashlytics")
}

android {
    namespace = "com.vidtele.app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Application ID pour VidTele
        applicationId = "com.vidtele.app"
        // Android 7.0 (API 24) minimum : choix validé en Phase 1 (≈ 99 % des appareils actifs)
        minSdk = 24
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        debug {
            manifestPlaceholders["admobAppId"] = "ca-app-pub-3940256099942544~3347511713"
        }
        // Build « profile » (mesures de performance sur téléphone) : identifiant AdMob de TEST
        getByName("profile") {
            manifestPlaceholders["admobAppId"] = "ca-app-pub-3940256099942544~3347511713"
        }
        release {
            manifestPlaceholders["admobAppId"] = "ca-app-pub-7846348811801616~6697457552"
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
