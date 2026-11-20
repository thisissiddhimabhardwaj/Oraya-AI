import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { useAuth } from "./context/AuthContext";
const Dashboard = lazy(() => import("./pages/Dashboard"));
import Landing from "./pages/Landing";
const LectureWorkspace = lazy(() => import("./pages/LectureWorkspace"));
const Library = lazy(() => import("./pages/Library"));
import Login from "./pages/Login";
const NewLecture = lazy(() => import("./pages/NewLecture"));
const Onboarding = lazy(() => import("./pages/Onboarding"));
const Progress = lazy(() => import("./pages/Progress"));
import Signup from "./pages/Signup";
const Flashcards = lazy(() => import("./pages/Flashcards"));
import { Loading } from "./components/ui";

const Exams = lazy(() => import("./pages/Exams"));
const Memory = lazy(() => import("./pages/Memory"));
const SpatialStudio = lazy(() => import("./pages/SpatialStudio"));
const Revision = lazy(() => import("./pages/Revision"));
const AskLibrary = lazy(() => import("./pages/AskLibrary"));
const Planner = lazy(() => import("./pages/Planner"));
const lazyPage = (el) => <Suspense fallback={<Loading />}>{el}</Suspense>;

function Protected({ children }) {
  const { user, booting } = useAuth();
  const location = useLocation();
  if (booting) {
    return (
      <div className="min-h-screen grid place-items-center">
        <Loading label="Starting ORAYA…" />
      </div>
    );
  }
  if (!user)
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}

export default function App() {
  const { user, booting } = useAuth();

  return (
    <Suspense fallback={<Loading label="Opening your learning space…" />}>
      <Routes>
        <Route
          path="/"
          element={user ? <Navigate to="/dashboard" replace /> : <Landing />}
        />
        <Route
          path="/login"
          element={user ? <Navigate to="/dashboard" replace /> : <Login />}
        />
        <Route
          path="/signup"
          element={user ? <Navigate to="/dashboard" replace /> : <Signup />}
        />

        <Route
          path="/onboarding"
          element={
            <Protected>
              <Onboarding />
            </Protected>
          }
        />

        <Route
          path="/dashboard"
          element={
            <Protected>
              <AppShell />
            </Protected>
          }
        >
          <Route index element={<Dashboard />} />
        </Route>

        <Route
          path="/"
          element={
            <Protected>
              <AppShell />
            </Protected>
          }
        >
          <Route path="learn/new" element={<NewLecture />} />
          <Route path="library" element={<Library />} />
          <Route path="flashcards" element={<Flashcards />} />
          <Route path="progress" element={<Progress />} />
          <Route path="revision" element={lazyPage(<Revision />)} />
          <Route path="ask" element={lazyPage(<AskLibrary />)} />
          <Route path="exams" element={lazyPage(<Exams />)} />
          <Route path="memory" element={lazyPage(<Memory />)} />
          <Route path="spatial" element={lazyPage(<SpatialStudio />)} />
          <Route path="planner" element={lazyPage(<Planner />)} />
          <Route path="lecture/:id" element={<LectureWorkspace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>

        <Route
          path="*"
          element={
            booting ? (
              <div className="min-h-screen grid place-items-center">
                <Loading />
              </div>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
      </Routes>
    </Suspense>
  );
}
