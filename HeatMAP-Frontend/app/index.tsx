import { Redirect } from 'expo-router';

/**
 * Root index page - redirects to the Map tab as the default landing page
 * The Map page contains the primary and most important system information
 */
export default function Index() {
  return <Redirect href="/(tabs)/map" />;
}
