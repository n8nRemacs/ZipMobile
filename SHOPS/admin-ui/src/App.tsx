import { Routes, Route, Link, Navigate } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  DashboardOutlined,
  AuditOutlined,
  BookOutlined,
} from '@ant-design/icons'
import ModerationList from './pages/ModerationList'
import Dashboard from './pages/Dashboard'
import Dictionaries from './pages/Dictionaries'

const { Header, Content, Sider } = Layout

export default function App() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible>
        <div style={{ color: '#fff', textAlign: 'center', padding: '16px', fontWeight: 'bold' }}>
          ZipMobile
        </div>
        <Menu theme="dark" mode="inline" defaultSelectedKeys={['moderation']} items={[
          { key: 'dashboard', icon: <DashboardOutlined />, label: <Link to="/dashboard">Dashboard</Link> },
          { key: 'moderation', icon: <AuditOutlined />, label: <Link to="/moderation">Moderation</Link> },
          { key: 'dictionaries', icon: <BookOutlined />, label: <Link to="/dictionaries">Dictionaries</Link> },
        ]} />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', fontWeight: 'bold', fontSize: 18 }}>
          ZipMobile Admin
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8 }}>
          <Routes>
            <Route path="/" element={<Navigate to="/moderation" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/moderation" element={<ModerationList />} />
            <Route path="/dictionaries" element={<Dictionaries />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}
