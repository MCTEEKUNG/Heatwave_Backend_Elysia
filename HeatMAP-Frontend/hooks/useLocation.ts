/**
 * Location Hook - Handles location permissions and GPS tracking
 * Cross-platform: Works on both web and native
 */

import { useState, useEffect, useCallback } from 'react';
import { Platform, PermissionsAndroid, Alert } from 'react-native';
import * as ExpoLocation from 'expo-location';

export type LocationStatus = 
  | 'idle'
  | 'requesting'
  | 'granted'
  | 'denied'
  | 'restricted'
  | 'unknown';

export interface LocationCoords {
  latitude: number;
  longitude: number;
  accuracy?: number | null;
  altitude?: number | null;
  heading?: number | null;
  speed?: number | null;
}

export interface UseLocationReturn {
  location: LocationCoords | null;
  status: LocationStatus;
  error: string | null;
  requestPermission: () => Promise<boolean>;
  getCurrentLocation: () => Promise<LocationCoords | null>;
  isLoading: boolean;
}

// Default location (Bangkok) as fallback
const DEFAULT_LOCATION: LocationCoords = {
  latitude: 13.7563,
  longitude: 100.5018,
};

export function useLocation(): UseLocationReturn {
  const [location, setLocation] = useState<LocationCoords | null>(null);
  const [status, setStatus] = useState<LocationStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Show permission explanation dialog
  const showPermissionExplanation = useCallback(() => {
    return new Promise<boolean>((resolve) => {
      Alert.alert(
        '📍 Location Access Required',
        'Heatwave Forecast needs your location to:\n\n' +
        '• Show heatwave predictions for your area\n' +
        '• Center the map on your current position\n' +
        '• Provide accurate local weather alerts\n\n' +
        'Your location data is only used to improve your experience and is never shared.',
        [
          {
            text: 'Allow Access',
            onPress: () => resolve(true),
          },
          {
            text: 'Deny',
            style: 'cancel',
            onPress: () => resolve(false),
          },
        ],
        { cancelable: false }
      );
    });
  }, []);

  // Request location permission
  const requestPermission = useCallback(async (): Promise<boolean> => {
    setIsLoading(true);
    setError(null);

    try {
      // Show explanation first
      const userConfirmed = await showPermissionExplanation();
      if (!userConfirmed) {
        setStatus('denied');
        setIsLoading(false);
        return false;
      }

      // Request permission based on platform
      if (Platform.OS === 'web') {
        // Web uses browser Geolocation API
        if ('geolocation' in navigator) {
          setStatus('requesting');
          const permission = await navigator.permissions.query({ name: 'geolocation' });
          
          if (permission.state === 'granted') {
            setStatus('granted');
            setIsLoading(false);
            return true;
          } else if (permission.state === 'prompt') {
            // Will trigger browser's own permission dialog
            setStatus('requesting');
            setIsLoading(false);
            return true;
          } else {
            setStatus('denied');
            setIsLoading(false);
            return false;
          }
        } else {
          setError('Geolocation not supported on this browser');
          setStatus('unknown');
          setIsLoading(false);
          return false;
        }
      } else {
        // Native (iOS/Android)
        const { status: permissionStatus } = await ExpoLocation.requestForegroundPermissionsAsync();
        
        if (permissionStatus === 'granted') {
          setStatus('granted');
          setIsLoading(false);
          return true;
        } else if (permissionStatus === 'denied') {
          setStatus('denied');
          setIsLoading(false);
          return false;
        } else {
          // Handle undetermined or other statuses
          setStatus('unknown');
          setIsLoading(false);
          return false;
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to request permission';
      setError(errorMessage);
      setStatus('unknown');
      setIsLoading(false);
      return false;
    }
  }, [showPermissionExplanation]);

  // Get current location
  const getCurrentLocation = useCallback(async (): Promise<LocationCoords | null> => {
    setIsLoading(true);
    setError(null);

    try {
      let coords: LocationCoords | null = null;

      if (Platform.OS === 'web') {
        // Web: Use browser Geolocation API
        if ('geolocation' in navigator) {
          coords = await new Promise<LocationCoords>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
              (position) => {
                resolve({
                  latitude: position.coords.latitude,
                  longitude: position.coords.longitude,
                  accuracy: position.coords.accuracy,
                  altitude: position.coords.altitude,
                  heading: position.coords.heading,
                  speed: position.coords.speed,
                });
              },
              (err) => {
                reject(new Error(err.message));
              },
              {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 60000,
              }
            );
          });
        } else {
          // Fallback to default
          coords = DEFAULT_LOCATION;
        }
      } else {
        // Native: Use Expo Location
        const hasPermission = await requestPermission();
        if (!hasPermission) {
          setIsLoading(false);
          return DEFAULT_LOCATION;
        }

        const position = await ExpoLocation.getCurrentPositionAsync({
          accuracy: ExpoLocation.Accuracy.High,
        });

        coords = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          altitude: position.coords.altitude,
          heading: position.coords.heading,
          speed: position.coords.speed,
        };
      }

      if (coords) {
        setLocation(coords);
        setStatus('granted');
      }

      setIsLoading(false);
      return coords;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get location';
      setError(errorMessage);
      
      // Return default location on error
      setLocation(DEFAULT_LOCATION);
      setIsLoading(false);
      return DEFAULT_LOCATION;
    }
  }, [requestPermission]);

  // Auto-request location on mount (optional)
  useEffect(() => {
    // Don't auto-request - let user trigger it
  }, []);

  return {
    location,
    status,
    error,
    requestPermission,
    getCurrentLocation,
    isLoading,
  };
}

export default useLocation;
